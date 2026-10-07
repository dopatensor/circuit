"""Compute matches and store them in the match cache (F4).

Flow for one member:
1. Candidates from two sources, merged:
   - local: same city AND (a shared trait, a 1-2 hop connection or the same sector)
   - bridge: anyone, any sector, whose offers meet the member's needs or whose needs
     the member's offers meet, by capability or by embedding similarity (pgvector).
2. Score every candidate with the pure functions in scoring.py.
3. Rank: capacity, one per group, ~25% bridge quota, sector diversity.
4. Write one reason per result.

Students are different: their candidates are jobs within a hard distance limit, scored
with the same skill match as the map and job pages.

Everything a round needs is loaded once (a MatchContext), so computing all ~300
members takes a few seconds.
"""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

import structlog
from sqlalchemy import func, select, text

from app.cache import CachedMatch, get_match_cache
from app.config import Settings
from app.geo import member_center, point
from app.graph import Adjacency, best_trust_path, get_graph
from app.jobs import job_roles, member_skills, startup_need_caps
from app.matching.ranking import Scored, rank
from app.matching.reasons import job_reason, match_reason
from app.matching.scoring import (
    SEM_FLOOR,
    Item,
    Party,
    Weights,
    is_bridge,
    score_pair,
    student_job_score,
)
from app.models import (
    Capability,
    IntroRequest,
    Job,
    Member,
    MemberTrait,
    Need,
    Offer,
    Startup,
    StartupMember,
    StartupTrait,
    Trait,
)
from app.skill_match import skill_match

log = structlog.get_logger("matching")

NETWORK_ROLES = ("founder", "mentor", "investor")
SIMS_PER_NEED = 25  # nearest offers fetched per need from the HNSW index


def weights_from(settings: Settings) -> Weights:
    return Weights(
        complementarity=settings.match_w_complementarity,
        affinity=settings.match_w_affinity,
        trust_path=settings.match_w_trust_path,
        timing=settings.match_w_timing,
        load_penalty=settings.match_w_load_penalty,
    )


@dataclass
class MatchContext:
    members: dict[uuid.UUID, Party]
    roles: dict[uuid.UUID, str]
    cities: dict[uuid.UUID, str | None]
    startups: dict[uuid.UUID, Party]
    teams: dict[uuid.UUID, set[uuid.UUID]]  # member -> startups they're on
    sims: dict[tuple[uuid.UUID, uuid.UUID], float]
    adjacency: Adjacency
    cap_names: dict[str, str]
    trait_names: dict[str, str]
    # offer id -> owner, need id -> owner, for semantic bridge candidates
    offer_owner: dict[uuid.UUID, uuid.UUID] = field(default_factory=dict)
    need_owner: dict[uuid.UUID, uuid.UUID] = field(default_factory=dict)
    sims_by_need: dict[uuid.UUID, list[tuple[uuid.UUID, float]]] = field(default_factory=dict)
    sims_by_offer: dict[uuid.UUID, list[tuple[uuid.UUID, float]]] = field(default_factory=dict)

    def __post_init__(self):
        for (nid, oid), sim in self.sims.items():
            self.sims_by_need.setdefault(nid, []).append((oid, sim))
            self.sims_by_offer.setdefault(oid, []).append((nid, sim))

    def name(self, pid: uuid.UUID) -> str:
        p = self.members.get(pid) or self.startups.get(pid)
        return p.name if p else "someone"


async def load_context(session) -> MatchContext:
    members = (await session.scalars(select(Member))).all()
    startups = (await session.scalars(select(Startup))).all()

    traits: dict[uuid.UUID, set[str]] = {}
    for mid, t in (
        await session.execute(select(MemberTrait.member_id, MemberTrait.trait_id))
    ).all():
        traits.setdefault(mid, set()).add(t)
    for sid, t in (
        await session.execute(select(StartupTrait.startup_id, StartupTrait.trait_id))
    ).all():
        traits.setdefault(sid, set()).add(t)

    needs: dict[uuid.UUID, list[Item]] = {}
    need_owner = {}
    for nid, owner, cap, created in (
        await session.execute(
            select(Need.id, Need.owner_id, Need.capability_id, Need.created_at).where(Need.active)
        )
    ).all():
        needs.setdefault(owner, []).append(Item(nid, cap, created))
        need_owner[nid] = owner
    offers: dict[uuid.UUID, list[Item]] = {}
    offer_owner = {}
    for oid, owner, cap, created in (
        await session.execute(
            select(Offer.id, Offer.member_id, Offer.capability_id, Offer.created_at).where(
                Offer.active
            )
        )
    ).all():
        offers.setdefault(owner, []).append(Item(oid, cap, created))
        offer_owner[oid] = owner

    teams: dict[uuid.UUID, set[uuid.UUID]] = {}
    for sid, mid in (
        await session.execute(select(StartupMember.startup_id, StartupMember.member_id))
    ).all():
        teams.setdefault(mid, set()).add(sid)
    for s in startups:
        if s.claimed_by_member_id:
            teams.setdefault(s.claimed_by_member_id, set()).add(s.id)

    pending = dict(
        (
            await session.execute(
                select(IntroRequest.to_member, func.count())
                .where(IntroRequest.status == "pending")
                .group_by(IntroRequest.to_member)
            )
        ).all()
    )

    member_parties = {}
    for m in members:
        # Founders bring their startup's needs too (minus duplicates).
        own = list(needs.get(m.id, []))
        seen = {n.capability_id for n in own}
        for sid in teams.get(m.id, ()):
            for n in needs.get(sid, []):
                if n.capability_id not in seen:
                    own.append(n)
                    seen.add(n.capability_id)
        member_parties[m.id] = Party(
            id=m.id,
            kind="member",
            name=m.display_name,
            sector=m.sector,
            traits=frozenset(traits.get(m.id, ())),
            needs=tuple(own),
            offers=tuple(offers.get(m.id, ())),
            open_intro_slots=m.open_intro_slots,
            pending_requests=pending.get(m.id, 0),
        )
    startup_parties = {
        s.id: Party(
            id=s.id,
            kind="startup",
            name=s.name,
            sector=s.sector,
            traits=frozenset(traits.get(s.id, ())),
            needs=tuple(needs.get(s.id, ())),
        )
        for s in startups
    }

    # Semantic need -> offer similarity, via the HNSW index (top-K per need).
    sims = {
        (nid, oid): float(sim)
        for nid, oid, sim in (
            await session.execute(
                text(
                    """
                    SELECT n.id, o.id, 1 - (o.embedding <=> n.embedding)
                    FROM needs n
                    CROSS JOIN LATERAL (
                        SELECT id, embedding FROM offers
                        WHERE active AND embedding IS NOT NULL
                        ORDER BY embedding <=> n.embedding
                        LIMIT :k
                    ) o
                    WHERE n.active AND n.embedding IS NOT NULL
                    """
                ),
                {"k": SIMS_PER_NEED},
            )
        ).all()
    }

    return MatchContext(
        members=member_parties,
        roles={m.id: m.role for m in members},
        cities={m.id: m.city for m in members},
        startups=startup_parties,
        teams=teams,
        sims=sims,
        adjacency=await get_graph().adjacency(session),
        cap_names=dict((await session.execute(select(Capability.id, Capability.name))).all()),
        trait_names=dict((await session.execute(select(Trait.id, Trait.name))).all()),
        offer_owner=offer_owner,
        need_owner=need_owner,
    )


# --- candidates -------------------------------------------------------------------------


def candidates(ctx: MatchContext, member_id: uuid.UUID) -> dict[uuid.UUID, str]:
    """{candidate id: "local" | "bridge" | "both"} for a network member."""
    me = ctx.members[member_id]
    my_startups = ctx.teams.get(member_id, set())
    pool = {pid: p for pid, p in ctx.members.items() if ctx.roles[pid] in NETWORK_ROLES}
    pool.pop(member_id, None)
    pool.update({sid: s for sid, s in ctx.startups.items() if sid not in my_startups})
    # People on my own startup's team aren't matches.
    for teammate, sids in ctx.teams.items():
        if sids & my_startups:
            pool.pop(teammate, None)

    source: dict[uuid.UUID, str] = {}

    def add(pid, kind):
        source[pid] = kind if source.get(pid) in (None, kind) else "both"

    # Local: same city and something in common.
    neighbours = ctx.adjacency.get(member_id, {})
    two_hop = {n2 for n in neighbours for n2 in ctx.adjacency.get(n, {})}
    for pid, p in pool.items():
        same_city = p.kind == "startup" or ctx.cities.get(pid) == ctx.cities.get(member_id)
        if same_city and (me.traits & p.traits or pid in neighbours or pid in two_hop or (
            me.sector and me.sector == p.sector
        )):  # fmt: skip
            add(pid, "local")

    # Bridge: need <-> offer across the whole pool, ignoring sector.
    my_need_caps = {n.capability_id for n in me.needs}
    my_offer_caps = {o.capability_id for o in me.offers}
    for pid, p in pool.items():
        if my_need_caps & {o.capability_id for o in p.offers} or my_offer_caps & {
            n.capability_id for n in p.needs
        }:
            add(pid, "bridge")
    for n in me.needs:  # semantically close offers (a different capability chip)
        for oid, sim in ctx.sims_by_need.get(n.id, ()):
            if sim >= SEM_FLOOR and ctx.offer_owner.get(oid) in pool:
                add(ctx.offer_owner[oid], "bridge")
    for o in me.offers:  # needs my offers fit semantically
        for nid, sim in ctx.sims_by_offer.get(o.id, ()):
            if sim >= SEM_FLOOR and ctx.need_owner.get(nid) in pool:
                add(ctx.need_owner[nid], "bridge")
    return source


def _group(ctx: MatchContext, pid: uuid.UUID) -> uuid.UUID:
    if pid in ctx.startups:
        return pid
    sids = ctx.teams.get(pid)
    return min(sids) if sids else pid


def network_matches(
    ctx: MatchContext, member_id: uuid.UUID, settings: Settings, now: datetime | None = None
) -> list[CachedMatch]:
    me = ctx.members[member_id]
    weights = weights_from(settings)
    scored: list[Scored] = []
    details = {}
    for pid, source in candidates(ctx, member_id).items():
        cand = ctx.members.get(pid) or ctx.startups[pid]
        path = best_trust_path(ctx.adjacency, member_id, pid) if cand.kind == "member" else None
        score, comps = score_pair(me, cand, ctx.sims, path, weights, now)
        if comps.complementarity == 0 and comps.affinity == 0:
            continue  # nothing to talk about
        bridge = is_bridge(me, cand, comps.complementarity)
        at_capacity = cand.kind == "member" and comps.load_penalty >= 1.0
        scored.append(Scored(pid, score, bridge, cand.sector, _group(ctx, pid), at_capacity))
        details[pid] = (cand, comps, bridge, source)

    out = []
    for s in rank(scored, settings.match_results_per_member, settings.match_bridge_share):
        cand, comps, bridge, source = details[s.candidate_id]
        reason = match_reason(
            cand.name,
            comps,
            is_bridge=bridge,
            member_sector=me.sector,
            candidate_sector=cand.sector,
            cap_names=ctx.cap_names,
            trait_names=ctx.trait_names,
            via_name=ctx.name(comps.via) if comps.via else None,
        )
        components = comps.as_dict() | {"source": source}
        out.append(
            CachedMatch(s.candidate_id, cand.kind, round(s.score, 4), components, reason, bridge)
        )
    return out


# --- students ---------------------------------------------------------------------------


async def student_matches(session, member_id: uuid.UUID, settings: Settings) -> list[CachedMatch]:
    """Jobs within the student's radius (hard filter), best skill match first, at most
    one job per startup so the list stays varied."""
    lat, lng = await member_center(session, member_id, settings)
    origin = point(lat, lng)
    radius = settings.student_radius_km
    distance_km = (func.ST_Distance(Startup.location, origin) / 1000.0).label("distance_km")
    rows = (
        await session.execute(
            select(Job, Startup.id.label("sid"), distance_km)
            .join(Startup, Startup.id == Job.startup_id)
            .where(Job.status == "open", func.ST_DWithin(Startup.location, origin, radius * 1000.0))
        )
    ).all()
    if not rows:
        return []
    sids = list({r.sid for r in rows})
    roles = {j["id"]: j for js in (await job_roles(session, sids)).values() for j in js}
    needs = await startup_need_caps(session, sids)
    skills = await member_skills(session, member_id)
    cap_names = dict((await session.execute(select(Capability.id, Capability.name))).all())

    best_per_startup: dict[uuid.UUID, CachedMatch] = {}
    for r in rows:
        role = roles.get(r.Job.id)
        if not role:
            continue
        m = skill_match(skills, [role], needs.get(r.sid, []))
        if m.score == 0:
            continue
        score = student_job_score(m.score, r.distance_km, radius)
        match = CachedMatch(
            candidate_id=r.Job.id,
            candidate_type="job",
            score=round(score, 4),
            components={
                "skill_match": m.score,
                "distance_km": round(r.distance_km, 2),
                "matched": m.matched,
                "missing": m.missing,
                "startup_id": str(r.sid),
            },
            reason=job_reason(m.score, m.matched, r.distance_km, r.Job.type, r.Job.paid, cap_names),
            is_bridge=False,
        )
        current = best_per_startup.get(r.sid)
        if current is None or match.score > current.score:
            best_per_startup[r.sid] = match
    ranked = sorted(best_per_startup.values(), key=lambda m: (-m.score, str(m.candidate_id)))
    return ranked[: settings.match_results_per_member]


# --- entry points -----------------------------------------------------------------------


async def compute_for_member(
    session, member_id: uuid.UUID, settings: Settings, ctx: MatchContext | None = None
) -> int:
    role = await session.scalar(select(Member.role).where(Member.id == member_id))
    if role == "student":
        matches = await student_matches(session, member_id, settings)
    elif role in NETWORK_ROLES:
        ctx = ctx or await load_context(session)
        matches = network_matches(ctx, member_id, settings)
    else:
        matches = []  # partner admins use the dashboard instead
    await get_match_cache().put(session, member_id, matches)
    return len(matches)


async def compute_all(session, settings: Settings) -> dict[str, int]:
    started = datetime.now(UTC)
    ctx = await load_context(session)
    members = (await session.execute(select(Member.id, Member.role))).all()
    total = 0
    for mid, _role in members:
        total += await compute_for_member(session, mid, settings, ctx)
    seconds = (datetime.now(UTC) - started).total_seconds()
    log.info("matches_computed", members=len(members), results=total, seconds=round(seconds, 2))
    return {"members": len(members), "results": total}
