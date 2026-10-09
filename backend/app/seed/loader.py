"""Write a seed Dataset into Postgres.

load_dataset() is idempotent: running it twice leaves the database exactly as running
it once. Startups are upserted by website_domain (the crawler's natural key); every
other seeded row has a deterministic id, so "insert ... on conflict update" works.

Live activity is preserved by a plain re-seed: claims made in the app are kept and
view counts only ever go up. reset_demo() is the "back to a known state" button: it
empties every table first, then loads the seed.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, insert, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Base,
    Capability,
    Connection,
    Event,
    GitHubAccount,
    GitHubRepo,
    IntroRequest,
    Job,
    JobCapability,
    Member,
    MemberSkill,
    MemberTrait,
    Need,
    Offer,
    ProofItem,
    Startup,
    StartupMember,
    StartupTrait,
    Trait,
)
from app.seed.catalog import CAPABILITIES, TRAITS
from app.seed.ids import member_id, seed_uuid, startup_id
from app.seed.schema import Dataset, StartupRecord


def _point(lat: float, lng: float) -> str:
    return f"SRID=4326;POINT({lng} {lat})"  # WKT is (longitude latitude)


async def _upsert(session: AsyncSession, model, rows: list[dict], key: list[str], update: dict):
    if rows:
        stmt = pg_insert(model).values(rows)
        set_ = {col: getattr(stmt.excluded, col) for col in update.get("cols", [])}
        set_.update(update.get("exprs", {}))
        if set_:
            stmt = stmt.on_conflict_do_update(index_elements=key, set_=set_)
        else:
            stmt = stmt.on_conflict_do_nothing(index_elements=key)
        await session.execute(stmt)


async def upsert_catalog(session: AsyncSession) -> None:
    await _upsert(
        session,
        Capability,
        [c._asdict() for c in CAPABILITIES],
        ["id"],
        {"cols": ["name", "category", "description"]},
    )
    await _upsert(
        session, Trait, [t._asdict() for t in TRAITS], ["id"], {"cols": ["name", "description"]}
    )


async def upsert_startup_records(
    session: AsyncSession, records: list[StartupRecord], view_counts: dict[str, int] | None = None
) -> dict[str, object]:
    """Upsert crawler-shaped records by website_domain. Returns {domain: startup id}.

    This is the function a future crawler job will call too.
    """
    view_counts = view_counts or {}
    rows = [
        {
            "id": startup_id(r.website_domain),
            "name": r.name,
            "website_domain": r.website_domain,
            "description": r.description,
            "sector": r.sector,
            "stage": r.stage,
            "address": r.address,
            "location": _point(r.lat, r.lng),
            "hiring": r.hiring,
            "open_roles": [role.model_dump() for role in r.open_roles],
            "tech_stack": r.tech_stack,
            "source": r.source,
            "view_count": view_counts.get(r.website_domain, 0),
        }
        for r in records
    ]
    if not rows:
        return {}
    stmt = pg_insert(Startup).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["website_domain"],
        set_={
            **{
                col: getattr(stmt.excluded, col)
                for col in (
                    "name",
                    "description",
                    "sector",
                    "stage",
                    "address",
                    "location",
                    "hiring",
                    "open_roles",
                    "tech_stack",
                )  # fmt: skip
            },
            # Never lower a live counter.
            "view_count": func.greatest(Startup.view_count, stmt.excluded.view_count),
        },
    ).returning(Startup.website_domain, Startup.id)
    result = await session.execute(stmt)
    return {domain: id_ for domain, id_ in result}


async def load_dataset(session: AsyncSession, data: Dataset) -> None:
    await upsert_catalog(session)

    # --- members ---
    member_ids = {m.key: member_id(m.key) for m in data.members}
    await _upsert(
        session,
        Member,
        [
            {
                "id": member_ids[m.key],
                "auth_subject": f"demo:{m.key}",  # only usable when DEMO_AUTH is on
                "role": m.role,
                "display_name": m.display_name,
                "bio": m.bio,
                "sector": m.sector,
                "location": _point(m.lat, m.lng),
                "city": m.city,
                "college": m.college,
                "verification_level": m.verification_level,
                "open_intro_slots": m.open_intro_slots,
                "circuits_opt_in": m.circuits_opt_in,
            }
            for m in data.members
        ],
        ["id"],
        {
            "cols": [
                "auth_subject",
                "role",
                "display_name",
                "bio",
                "sector",
                "location",
                "city",
                "college",
                "verification_level",
                "open_intro_slots",
                "circuits_opt_in",
            ]  # fmt: skip
        },
    )

    # --- startups ---
    startup_ids = await upsert_startup_records(
        session,
        [s.record for s in data.startups],
        {s.record.website_domain: s.view_count for s in data.startups},
    )
    for s in data.startups:  # keep any claim made in the app; only fill empty ones
        if s.claimed_by:
            await session.execute(
                Startup.__table__.update()
                .where(Startup.id == startup_ids[s.record.website_domain])
                .where(Startup.claimed_by_member_id.is_(None))
                .values(claimed_by_member_id=member_ids[s.claimed_by])
            )

    # --- link tables: replace the seeded owners' rows ---
    seeded_members = list(member_ids.values())
    seeded_startups = list(startup_ids.values())
    await session.execute(delete(MemberTrait).where(MemberTrait.member_id.in_(seeded_members)))
    await session.execute(delete(MemberSkill).where(MemberSkill.member_id.in_(seeded_members)))
    await session.execute(delete(StartupTrait).where(StartupTrait.startup_id.in_(seeded_startups)))
    await session.execute(
        delete(StartupMember).where(StartupMember.startup_id.in_(seeded_startups))
    )
    rows = [{"member_id": member_ids[m.key], "trait_id": t} for m in data.members for t in m.traits]
    if rows:
        await session.execute(insert(MemberTrait), rows)
    rows = [
        {"member_id": member_ids[m.key], "capability_id": c, "level": lvl}
        for m in data.members
        for c, lvl in m.skills.items()
    ]
    if rows:
        await session.execute(insert(MemberSkill), rows)
    rows = [
        {"startup_id": startup_ids[s.record.website_domain], "trait_id": t}
        for s in data.startups
        for t in s.traits
    ]
    if rows:
        await session.execute(insert(StartupTrait), rows)
    rows = [
        {"startup_id": startup_ids[s.record.website_domain], "member_id": member_ids[k], "title": t}
        for s in data.startups
        for k, t in s.team
    ]
    if rows:
        await session.execute(insert(StartupMember), rows)

    # --- jobs (F11): one per open role; ids are stable so applications survive a re-seed
    job_rows, job_caps = [], []
    for s in data.startups:
        for i, j in enumerate(s.jobs):
            jid = seed_uuid("job", f"{s.record.website_domain}:{i}")
            job_rows.append(
                {
                    "id": jid,
                    "startup_id": startup_ids[s.record.website_domain],
                    "title": j.title,
                    "description": j.description,
                    "type": j.type,
                    "paid": j.paid,
                    "compensation": j.compensation,
                    "source": "seed",
                }
            )
            job_caps += [
                {"job_id": jid, "capability_id": c, "min_level": lvl}
                for c, lvl in j.capabilities.items()
            ]
    if job_rows:
        await _upsert(
            session,
            Job,
            job_rows,
            ["id"],
            {"cols": ["title", "description", "type", "paid", "compensation"]},
        )
        await session.execute(
            delete(JobCapability).where(JobCapability.job_id.in_([r["id"] for r in job_rows]))
        )
        await session.execute(insert(JobCapability), job_caps)

    # --- needs and offers (embeddings are filled in later by the matching job) ---
    need_rows = []
    for m in data.members:
        for i, n in enumerate(m.needs):
            need_rows.append(
                {
                    "id": seed_uuid("need", f"member:{m.key}:{i}"),
                    "owner_type": "member",
                    "owner_id": member_ids[m.key],
                    "capability_id": n.capability_id,
                    "text": n.text,
                }
            )
    for s in data.startups:
        for i, n in enumerate(s.needs):
            need_rows.append(
                {
                    "id": seed_uuid("need", f"startup:{s.record.website_domain}:{i}"),
                    "owner_type": "startup",
                    "owner_id": startup_ids[s.record.website_domain],
                    "capability_id": n.capability_id,
                    "text": n.text,
                }
            )
    offer_rows = [
        {
            "id": seed_uuid("offer", f"{m.key}:{i}"),
            "member_id": member_ids[m.key],
            "capability_id": o.capability_id,
            "text": o.text,
        }
        for m in data.members
        for i, o in enumerate(m.offers)
    ]
    for model, rows in ((Need, need_rows), (Offer, offer_rows)):
        if not rows:
            continue
        stmt = pg_insert(model).values(rows)
        table = model.__tablename__
        await session.execute(
            stmt.on_conflict_do_update(
                index_elements=["id"],
                set_={
                    "capability_id": stmt.excluded.capability_id,
                    "text": stmt.excluded.text,
                    "active": True,
                    # Keep a computed embedding only while its text is unchanged.
                    "embedding": text(
                        f"CASE WHEN {table}.text = excluded.text THEN {table}.embedding END"
                    ),
                },
            )
        )

    # --- connections (stored once per pair, smaller id first) ---
    conn_rows = []
    for c in data.connections:
        a, b = sorted((member_ids[c.a], member_ids[c.b]))
        conn_rows.append(
            {
                "id": seed_uuid("connection", f"{a}:{b}"),
                "member_a": a,
                "member_b": b,
                "strength": c.strength,
                "source": c.source,
            }
        )
    stmt = pg_insert(Connection).values(conn_rows)
    await session.execute(
        stmt.on_conflict_do_update(
            constraint="uq_connections_pair",
            set_={"strength": stmt.excluded.strength, "source": stmt.excluded.source},
        )
    )

    # --- history: past intros and student interest events ---
    now = datetime.now(UTC)
    intro_rows = [
        {
            "id": seed_uuid("intro", i.key),
            "from_member": member_ids[i.from_member],
            "to_member": member_ids[i.to_member],
            "via_member": member_ids[i.via_member] if i.via_member else None,
            "status": i.status,
            "reason": i.reason,
            "is_bridge": i.is_bridge,
            "outcome_rating": i.outcome_rating,
            "created_at": now - timedelta(days=i.days_ago),
            "responded_at": now - timedelta(days=i.days_ago - 1),
            "completed_at": now - timedelta(days=max(i.days_ago - 7, 0))
            if i.status == "completed"
            else None,
        }
        for i in data.intros
    ]
    if intro_rows:
        await session.execute(pg_insert(IntroRequest).values(intro_rows).on_conflict_do_nothing())

    # --- proof of work (R2): saved GitHub imports and non-code items ---
    # Insert-only: a plain re-seed keeps what students changed (featured, hidden, or
    # disconnected and reconnected); reset-demo starts from empty tables anyway.
    for gh in data.github:
        mid = member_ids[gh.member]
        await session.execute(
            pg_insert(GitHubAccount)
            .values(
                member_id=mid,
                github_user_id=gh.github_user_id,
                login=gh.login,
                profile_url=f"https://github.example/{gh.login}",
                homepage_url=gh.homepage_url,
                access_token_enc=None,  # no token: the weekly refresh skips seeded rows
                source="seed",
                status="ok",
                external_prs=[
                    {
                        "repo": p["repo"],
                        "url": p["url"],
                        "merged_at": (now - timedelta(days=p["days_ago"])).isoformat(),
                    }
                    for p in gh.external_prs
                ],
                external_prs_total=len(gh.external_prs),
                active_weeks_90d=gh.active_weeks_90d,
                last_active_at=now - timedelta(days=gh.last_active_days_ago)
                if gh.last_active_days_ago is not None
                else None,
                connected_at=now - timedelta(days=30),
                fetched_at=now - timedelta(days=2),
                next_fetch_at=None,
            )
            .on_conflict_do_nothing()
        )
        repo_rows = [
            {
                "id": seed_uuid("github_repo", f"{gh.member}/{r.key}"),
                "member_id": mid,
                "github_repo_id": gh.github_user_id * 100 + i,
                "name": r.name,
                "html_url": f"https://github.example/{gh.login}/{r.name}",
                "description": r.description,
                "homepage_url": r.homepage_url,
                "primary_language": max(r.languages, key=r.languages.get) if r.languages else None,
                "languages": r.languages,
                "frameworks": r.frameworks,
                "commits_by_user": r.commits_by_user,
                "commits_total": r.commits_total,
                "readme_excerpt": r.readme_excerpt,
                "pushed_at": now - timedelta(days=r.pushed_days_ago),
                "featured": r.featured,
                "hidden": False,
            }
            for i, r in enumerate(gh.repos)
        ]
        # Only when the account row is the seeded one (a student may have reconnected).
        seeded = await session.scalar(
            select(GitHubAccount.source).where(GitHubAccount.member_id == mid)
        )
        if repo_rows and seeded == "seed":
            await session.execute(pg_insert(GitHubRepo).values(repo_rows).on_conflict_do_nothing())
    if data.proof_items:
        await session.execute(
            pg_insert(ProofItem)
            .values(
                [
                    {
                        "id": seed_uuid("proof_item", p.key),
                        "member_id": member_ids[p.member],
                        "kind": p.kind,
                        "url": p.url,
                        "title": p.title,
                        "description": p.description,
                        "capability_ids": p.capability_ids,
                    }
                    for p in data.proof_items
                ]
            )
            .on_conflict_do_nothing()
        )

    # events is append-only, so seeded events are written once and never duplicated.
    already = await session.scalar(
        select(func.count()).select_from(Event).where(Event.payload["seed"].as_boolean())
    )
    if not already and data.events:
        await session.execute(
            insert(Event),
            [
                {
                    "actor_id": member_ids[e.actor] if e.actor else None,
                    "type": e.type,
                    "target_type": e.target_type,
                    "target_id": str(
                        startup_ids[e.target_key]
                        if e.target_type == "startup"
                        else member_ids[e.target_key]
                    )
                    if e.target_key
                    else None,
                    "payload": {**e.payload, "seed": True},
                    "created_at": now - timedelta(days=e.days_ago),
                }
                for e in data.events
            ],
        )


async def truncate_all(session: AsyncSession) -> None:
    """Empty every app table. TRUNCATE is allowed on the append-only events table."""
    tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
    await session.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
