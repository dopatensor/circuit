"""Loading jobs and computing a student's match to them (F11).

The same skill_match() function scores map pins, job lists and (Phase 4) matches,
so a student sees one consistent number everywhere.
"""

import uuid

from sqlalchemy import select

from app.models import Job, JobCapability, MemberSkill, Need
from app.schemas import RoleFitOut, SkillMatchOut
from app.skill_match import skill_match


async def job_roles(
    session, startup_ids: list[uuid.UUID], only_open: bool = True
) -> dict[uuid.UUID, list[dict]]:
    """{startup_id: [{"id", "title", "type", "paid", "capabilities", "min_levels"}]}"""
    if not startup_ids:
        return {}
    filters = [Job.startup_id.in_(startup_ids)]
    if only_open:
        filters.append(Job.status == "open")
    jobs = (
        await session.scalars(select(Job).where(*filters).order_by(Job.created_at, Job.title))
    ).all()
    caps: dict[uuid.UUID, dict[str, int]] = {}
    if jobs:
        for job_id, cap, lvl in (
            await session.execute(
                select(JobCapability.job_id, JobCapability.capability_id, JobCapability.min_level)
                .where(JobCapability.job_id.in_([j.id for j in jobs]))
                .order_by(JobCapability.capability_id)
            )
        ).all():
            caps.setdefault(job_id, {})[cap] = lvl
    out: dict[uuid.UUID, list[dict]] = {}
    for j in jobs:
        c = caps.get(j.id, {})
        out.setdefault(j.startup_id, []).append(
            {
                "id": j.id,
                "title": j.title,
                "type": j.type,
                "paid": j.paid,
                "compensation": j.compensation,
                "capabilities": list(c),
                "min_levels": c,
            }
        )
    return out


async def startup_need_caps(session, startup_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[str]]:
    if not startup_ids:
        return {}
    out: dict[uuid.UUID, list[str]] = {}
    for owner, cap in (
        await session.execute(
            select(Need.owner_id, Need.capability_id).where(
                Need.owner_type == "startup", Need.owner_id.in_(startup_ids), Need.active
            )
        )
    ).all():
        out.setdefault(owner, []).append(cap)
    return out


async def member_skills(session, member_id: uuid.UUID) -> dict[str, int]:
    return dict(
        (
            await session.execute(
                select(MemberSkill.capability_id, MemberSkill.level).where(
                    MemberSkill.member_id == member_id
                )
            )
        ).all()
    )


def match_out(skills: dict[str, int], roles: list[dict], needs: list[str]) -> SkillMatchOut:
    m = skill_match(skills, roles, needs)
    best = m.best_role
    return SkillMatchOut(
        score=m.score,
        best_role=RoleFitOut(
            title=best.title,
            score=round(best.score * 100),
            matched=best.matched,
            missing=best.missing,
        )
        if best
        else None,
        matched=m.matched,
        missing=m.missing,
    )
