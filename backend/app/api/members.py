"""Member profiles: your own (/me) and other people's."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import delete, func, or_, select

from app.auth import (
    LEVEL_BROWSE,
    CurrentUser,
    CurrentUserDep,
    SessionDep,
    TokenClaims,
    get_token_claims,
    require_level,
)
from app.events import record_event
from app.models import Member, MemberSkill, MemberTrait, Need, Offer
from app.profiles import member_me, member_public, point_wkt
from app.schemas import (
    MemberCreate,
    MemberMe,
    MemberPublic,
    MemberSummary,
    MemberUpdate,
    NeedIn,
    NeedOut,
    OfferIn,
    OfferOut,
    Page,
    SkillsIn,
    TraitsIn,
)

router = APIRouter(prefix="/api/members", tags=["members"])
BrowseUser = Annotated[CurrentUser, Depends(require_level(LEVEL_BROWSE))]


async def _me(session, user: CurrentUser) -> Member:
    return await session.get_one(Member, user.member_id)


@router.post("/me", response_model=MemberMe, status_code=status.HTTP_201_CREATED)
async def create_my_profile(
    body: MemberCreate,
    request: Request,
    claims: Annotated[TokenClaims, Depends(get_token_claims)],
    session: SessionDep,
) -> MemberMe:
    """First step after signing up: create your profile."""
    if await session.scalar(select(Member.id).where(Member.auth_subject == claims.subject)):
        raise HTTPException(status.HTTP_409_CONFLICT, detail="You already have a profile")
    member = Member(
        auth_subject=claims.subject,
        role=body.role,
        display_name=body.display_name,
        bio=body.bio,
        sector=body.sector,
        city=body.city,
        college=body.college if body.role == "student" else None,
        location=point_wkt(body.location) if body.location else None,
        # A provider-verified email (level 1) carries over; anything higher needs proof.
        verification_level=min(claims.verification_level or 0, LEVEL_BROWSE),
        open_intro_slots=2 if body.role == "student" else 3,
        circuits_opt_in=body.role != "student",
    )
    session.add(member)
    await session.flush()
    request.state.user_id = str(member.id)
    await record_event(session, "member.created", actor_id=member.id, payload={"role": member.role})
    await session.commit()
    return await member_me(session, member, claims.is_demo)


@router.get("/me", response_model=MemberMe)
async def get_my_profile(user: CurrentUserDep, session: SessionDep) -> MemberMe:
    return await member_me(session, await _me(session, user), user.claims.is_demo)


@router.patch("/me", response_model=MemberMe)
async def update_my_profile(body: MemberUpdate, user: CurrentUserDep, session: SessionDep):
    member = await _me(session, user)
    changes = body.model_dump(exclude_unset=True)
    if "location" in changes:
        member.location = point_wkt(body.location) if body.location else None
        changes.pop("location")
    if "linkedin_url" in changes:
        member.linkedin_url = str(body.linkedin_url) if body.linkedin_url else None
        changes.pop("linkedin_url")
        # F7 level 2: an email-verified member who adds a LinkedIn profile.
        if member.linkedin_url and member.verification_level == 1:
            member.verification_level = 2
            await record_event(
                session,
                "member.verification_changed",
                actor_id=member.id,
                target_type="member",
                target_id=member.id,
                payload={"level": 2, "via": "linkedin"},
            )
    if "college" in changes and member.role != "student":
        changes.pop("college")
    for field, value in changes.items():
        setattr(member, field, value)
    await record_event(
        session,
        "member.updated",
        actor_id=member.id,
        payload={"fields": sorted(body.model_dump(exclude_unset=True))},
    )
    await session.commit()
    await session.refresh(member)
    return await member_me(session, member, user.claims.is_demo)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_profile(user: CurrentUserDep, session: SessionDep) -> Response:
    """Delete your profile and everything attached to it."""
    await session.execute(
        delete(Need).where(Need.owner_type == "member", Need.owner_id == user.member_id)
    )
    await session.execute(delete(Member).where(Member.id == user.member_id))
    await record_event(session, "member.deleted", actor_id=user.member_id)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/me/traits", response_model=MemberMe)
async def set_my_traits(body: TraitsIn, user: CurrentUserDep, session: SessionDep):
    await session.execute(delete(MemberTrait).where(MemberTrait.member_id == user.member_id))
    session.add_all(MemberTrait(member_id=user.member_id, trait_id=t) for t in body.trait_ids)
    await record_event(
        session,
        "member.traits_set",
        actor_id=user.member_id,
        payload={"count": len(body.trait_ids)},
    )
    await session.commit()
    return await member_me(session, await _me(session, user), user.claims.is_demo)


@router.put("/me/skills", response_model=MemberMe)
async def set_my_skills(body: SkillsIn, user: CurrentUserDep, session: SessionDep):
    skills = {s.capability_id: s.level for s in body.skills}  # last one wins on duplicates
    await session.execute(delete(MemberSkill).where(MemberSkill.member_id == user.member_id))
    session.add_all(
        MemberSkill(member_id=user.member_id, capability_id=c, level=lvl)
        for c, lvl in skills.items()
    )
    await record_event(
        session, "member.skills_set", actor_id=user.member_id, payload={"count": len(skills)}
    )
    await session.commit()
    return await member_me(session, await _me(session, user), user.claims.is_demo)


@router.post("/me/needs", response_model=NeedOut, status_code=status.HTTP_201_CREATED)
async def add_my_need(body: NeedIn, user: CurrentUserDep, session: SessionDep) -> Need:
    need = Need(
        owner_type="member",
        owner_id=user.member_id,
        capability_id=body.capability_id,
        text=body.text,
    )
    session.add(need)
    await session.flush()
    await record_event(
        session,
        "need.created",
        actor_id=user.member_id,
        target_type="need",
        target_id=need.id,
        payload={"capability_id": need.capability_id, "owner_type": "member"},
    )
    await session.commit()
    await session.refresh(need)
    return need


@router.post("/me/offers", response_model=OfferOut, status_code=status.HTTP_201_CREATED)
async def add_my_offer(body: OfferIn, user: CurrentUserDep, session: SessionDep) -> Offer:
    offer = Offer(member_id=user.member_id, capability_id=body.capability_id, text=body.text)
    session.add(offer)
    await session.flush()
    await record_event(
        session,
        "offer.created",
        actor_id=user.member_id,
        target_type="offer",
        target_id=offer.id,
        payload={"capability_id": offer.capability_id},
    )
    await session.commit()
    await session.refresh(offer)
    return offer


@router.get("", response_model=Page[MemberSummary])
async def list_members(
    user: BrowseUser,
    session: SessionDep,
    role: str | None = None,
    sector: str | None = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[MemberSummary]:
    """Browse people (verification level 1+)."""
    filters = []
    if role:
        filters.append(Member.role == role)
    if sector:
        filters.append(Member.sector == sector)
    if q:
        like = f"%{q}%"
        filters.append(or_(Member.display_name.ilike(like), Member.bio.ilike(like)))
    total = await session.scalar(select(func.count()).select_from(Member).where(*filters))
    rows = await session.scalars(
        select(Member)
        .where(*filters)
        .order_by(Member.display_name, Member.id)
        .limit(limit)
        .offset(offset)
    )
    return Page[MemberSummary](
        items=[MemberSummary.model_validate(m) for m in rows],
        total=total or 0,
        limit=limit,
        offset=offset,
    )


@router.get("/{member_id}", response_model=MemberPublic)
async def get_member(member_id: uuid.UUID, user: BrowseUser, session: SessionDep):
    member = await session.get(Member, member_id)
    if member is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Member not found")
    await record_event(
        session, "member.viewed", actor_id=user.member_id, target_type="member", target_id=member.id
    )
    await session.commit()
    return await member_public(session, member)
