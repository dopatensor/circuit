"""Matches with reasons and Bridge badges (F4). Verification level 2 required."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from app.auth import (
    LEVEL_MATCHES,
    CurrentUser,
    SessionDep,
    SettingsDep,
    require_admin,
    require_level,
)
from app.cache import CachedMatch, get_match_cache
from app.embeddings import embed_pending, get_embedding_provider
from app.events import record_event
from app.matching.service import compute_all, compute_for_member
from app.models import Job, Member, Startup
from app.schemas import MatchList, MatchOut, RecomputeOut

router = APIRouter(prefix="/api", tags=["matches"])
MatchUser = Annotated[CurrentUser, Depends(require_level(LEVEL_MATCHES))]
ROLE_LABEL = {"founder": "Founder", "mentor": "Mentor", "investor": "Investor"}


async def _describe(session, matches: list[CachedMatch]) -> list[MatchOut]:
    ids = {
        t: [m.candidate_id for m in matches if m.candidate_type == t]
        for t in ("member", "startup", "job")
    }
    members = {
        m.id: m
        for m in (await session.scalars(select(Member).where(Member.id.in_(ids["member"])))).all()
    }
    startups = {
        s.id: s
        for s in (
            await session.scalars(select(Startup).where(Startup.id.in_(ids["startup"])))
        ).all()
    }
    jobs = {
        j.id: (j, s)
        for j, s in (
            await session.execute(
                select(Job, Startup)
                .join(Startup, Startup.id == Job.startup_id)
                .where(Job.id.in_(ids["job"]))
            )
        ).all()
    }
    out = []
    for m in matches:
        if m.candidate_type == "member" and m.candidate_id in members:
            p = members[m.candidate_id]
            title, sector, intro_to = p.display_name, p.sector, p.id
            subtitle = " · ".join(x for x in (ROLE_LABEL.get(p.role, p.role), p.sector) if x)
        elif m.candidate_type == "startup" and m.candidate_id in startups:
            s = startups[m.candidate_id]
            title, sector, intro_to = s.name, s.sector, s.claimed_by_member_id
            subtitle = f"Startup · {s.sector}" + (
                "" if s.claimed_by_member_id else " · not on Circuit yet"
            )
        elif m.candidate_type == "job" and m.candidate_id in jobs:
            j, s = jobs[m.candidate_id]
            title, sector, intro_to = j.title, s.sector, None
            subtitle = f"{s.name} · {j.compensation or ('paid' if j.paid else 'unpaid')}"
        else:
            continue  # the candidate was deleted since the last computation
        out.append(
            MatchOut(
                candidate_type=m.candidate_type,
                candidate_id=m.candidate_id,
                title=title,
                subtitle=subtitle,
                sector=sector,
                score=round(m.score * 100),
                reason=m.reason,
                is_bridge=m.is_bridge,
                intro_member_id=intro_to,
                components=m.components,
                computed_at=m.computed_at,
            )
        )
    return out


@router.get("/matches", response_model=MatchList)
async def my_matches(
    user: MatchUser,
    session: SessionDep,
    settings: SettingsDep,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> MatchList:
    """Your ranked matches, each with a one-line reason. Bridge matches (across
    sectors) are flagged. Results come from the precomputed cache; if you have none
    yet, they are computed now."""
    cache = get_match_cache()
    matches = await cache.get(session, user.member_id)
    if matches is None:
        await compute_for_member(session, user.member_id, settings)
        await session.commit()
        matches = await cache.get(session, user.member_id) or []
    items = (await _describe(session, matches))[:limit]
    await record_event(
        session, "matches.viewed", actor_id=user.member_id,
        payload={"count": len(items), "bridges": sum(i.is_bridge for i in items)},
    )  # fmt: skip
    await session.commit()
    return MatchList(items=items, computed_at=items[0].computed_at if items else None)


@router.post("/matches/refresh", response_model=MatchList)
async def refresh_my_matches(
    user: MatchUser, session: SessionDep, settings: SettingsDep
) -> MatchList:
    """Recompute your matches now (e.g. right after editing your needs and offers)."""
    await embed_pending(session, get_embedding_provider(settings))
    await compute_for_member(session, user.member_id, settings)
    await record_event(session, "matches.refreshed", actor_id=user.member_id)
    await session.commit()
    items = await _describe(session, await get_match_cache().get(session, user.member_id) or [])
    return MatchList(items=items, computed_at=items[0].computed_at if items else None)


@router.post("/admin/matches/recompute", response_model=RecomputeOut)
async def recompute_all(
    admin: Annotated[CurrentUser, Depends(require_admin())],
    session: SessionDep,
    settings: SettingsDep,
) -> RecomputeOut:
    """Run the background matching job now, for everyone."""
    embedded = await embed_pending(session, get_embedding_provider(settings))
    result = await compute_all(session, settings)
    await record_event(session, "matches.recomputed", actor_id=admin.member_id, payload=result)
    await session.commit()
    return RecomputeOut(embedded=embedded, **result)
