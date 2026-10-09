"""Assemble full member and startup profiles from their tables."""

import uuid

from geoalchemy2 import Geometry
from sqlalchemy import cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Member,
    MemberSkill,
    MemberTrait,
    Need,
    Offer,
    Startup,
    StartupMember,
    StartupTrait,
)
from app.schemas import (
    JobBrief,
    LatLng,
    MemberMe,
    MemberPublic,
    MemberSummary,
    NeedOut,
    OfferOut,
    SkillIn,
    StartupLink,
    StartupOut,
)


def point_wkt(p: LatLng) -> str:
    return f"SRID=4326;POINT({p.lng} {p.lat})"


def lat_lng_columns(column):
    """(lat, lng) SQL expressions for a geography point column."""
    geom = cast(column, Geometry)
    return func.ST_Y(geom).label("lat"), func.ST_X(geom).label("lng")


async def _location(session: AsyncSession, model, id_: uuid.UUID) -> LatLng | None:
    lat, lng = lat_lng_columns(model.location)
    row = (await session.execute(select(lat, lng).where(model.id == id_))).one_or_none()
    if row is None or row.lat is None:
        return None
    return LatLng(lat=row.lat, lng=row.lng)


async def member_public(session: AsyncSession, member: Member) -> MemberPublic:
    traits = (
        await session.scalars(
            select(MemberTrait.trait_id).where(MemberTrait.member_id == member.id)
        )
    ).all()
    offers = (
        await session.scalars(
            select(Offer)
            .where(Offer.member_id == member.id, Offer.active)
            .order_by(Offer.created_at)
        )
    ).all()
    needs = (
        await session.scalars(
            select(Need)
            .where(Need.owner_type == "member", Need.owner_id == member.id, Need.active)
            .order_by(Need.created_at)
        )
    ).all()
    startups = (
        await session.execute(
            select(
                Startup.id,
                Startup.name,
                StartupMember.title,
                (Startup.claimed_by_member_id == member.id).label("is_claimer"),
            )
            .join(StartupMember, StartupMember.startup_id == Startup.id)
            .where(StartupMember.member_id == member.id)
        )
    ).all()
    return MemberPublic(
        id=member.id,
        role=member.role,
        display_name=member.display_name,
        bio=member.bio,
        sector=member.sector,
        city=member.city,
        college=member.college,
        verification_level=member.verification_level,
        trait_ids=sorted(traits),
        offers=[OfferOut.model_validate(o) for o in offers],
        needs=[NeedOut.model_validate(n) for n in needs],
        startups=[
            StartupLink(
                startup_id=s.id, name=s.name, title=s.title, is_claimer=bool(s.is_claimer)
            )
            for s in startups
        ],
    )


async def member_me(session: AsyncSession, member: Member, is_demo: bool) -> MemberMe:
    public = await member_public(session, member)
    skills = (
        await session.execute(
            select(MemberSkill.capability_id, MemberSkill.level)
            .where(MemberSkill.member_id == member.id)
            .order_by(MemberSkill.capability_id)
        )
    ).all()
    return MemberMe(
        **public.model_dump(),
        location=await _location(session, Member, member.id),
        linkedin_url=member.linkedin_url,
        open_intro_slots=member.open_intro_slots,
        circuits_opt_in=member.circuits_opt_in,
        skills=[SkillIn(capability_id=c, level=lvl) for c, lvl in skills],
        is_demo=is_demo,
    )


async def startup_out(session: AsyncSession, startup: Startup) -> StartupOut:
    from app.jobs import job_roles  # local import: app.jobs imports from this module's deps

    traits = (
        await session.scalars(
            select(StartupTrait.trait_id).where(StartupTrait.startup_id == startup.id)
        )
    ).all()
    needs = (
        await session.scalars(
            select(Need)
            .where(Need.owner_type == "startup", Need.owner_id == startup.id, Need.active)
            .order_by(Need.created_at)
        )
    ).all()
    team = (
        await session.scalars(
            select(Member)
            .join(StartupMember, StartupMember.member_id == Member.id)
            .where(StartupMember.startup_id == startup.id)
        )
    ).all()
    return StartupOut(
        id=startup.id,
        name=startup.name,
        website_domain=startup.website_domain,
        description=startup.description,
        sector=startup.sector,
        stage=startup.stage,
        address=startup.address,
        location=await _location(session, Startup, startup.id),
        hiring=startup.hiring,
        jobs=[
            JobBrief(**{k: j[k] for k in ("id", "title", "type", "paid", "compensation")})
            for j in (await job_roles(session, [startup.id])).get(startup.id, [])
        ],
        tech_stack=startup.tech_stack,
        claimed=startup.claimed_by_member_id is not None,
        claimed_by_member_id=startup.claimed_by_member_id,
        source=startup.source,
        view_count=startup.view_count,
        trait_ids=sorted(traits),
        needs=[NeedOut.model_validate(n) for n in needs],
        team=[MemberSummary.model_validate(m) for m in team],
    )
