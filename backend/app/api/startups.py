"""Startup profiles. Anyone verified can browse; only the claimer can edit."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError

from app.auth import LEVEL_BROWSE, CurrentUser, CurrentUserDep, SessionDep, require_level
from app.events import record_event
from app.models import Need, Startup, StartupMember
from app.profiles import point_wkt, startup_out
from app.schemas import NeedIn, NeedOut, Page, StartupCreate, StartupOut, StartupUpdate

router = APIRouter(prefix="/api/startups", tags=["startups"])
BrowseUser = Annotated[CurrentUser, Depends(require_level(LEVEL_BROWSE))]


async def _get(session, startup_id: uuid.UUID) -> Startup:
    startup = await session.get(Startup, startup_id)
    if startup is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Startup not found")
    return startup


def _require_claimer(startup: Startup, user: CurrentUser) -> None:
    if startup.claimed_by_member_id != user.member_id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Only the founder who claimed this startup can edit it",
        )


@router.get("", response_model=Page[StartupOut])
async def list_startups(
    user: BrowseUser,
    session: SessionDep,
    sector: str | None = None,
    hiring: bool | None = None,
    claimed: bool | None = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[StartupOut]:
    filters = []
    if sector:
        filters.append(Startup.sector == sector)
    if hiring is not None:
        filters.append(Startup.hiring == hiring)
    if claimed is not None:
        filters.append(
            Startup.claimed_by_member_id.is_not(None)
            if claimed
            else Startup.claimed_by_member_id.is_(None)
        )
    if q:
        like = f"%{q}%"
        filters.append(or_(Startup.name.ilike(like), Startup.description.ilike(like)))
    total = await session.scalar(select(func.count()).select_from(Startup).where(*filters))
    rows = (
        await session.scalars(
            select(Startup)
            .where(*filters)
            .order_by(Startup.name, Startup.id)
            .limit(limit)
            .offset(offset)
        )
    ).all()
    return Page[StartupOut](
        items=[await startup_out(session, s) for s in rows],
        total=total or 0,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=StartupOut, status_code=status.HTTP_201_CREATED)
async def create_startup(body: StartupCreate, user: CurrentUserDep, session: SessionDep):
    """Founders add a startup we don't know yet. It starts claimed by them."""
    if user.role != "founder":
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Only founders can add startups")
    existing = await session.scalar(
        select(Startup.id).where(Startup.website_domain == body.website_domain)
    )
    if existing:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={
                "message": "This startup is already listed; claim it instead",
                "startup_id": str(existing),
            },
        )
    startup = Startup(
        **body.model_dump(exclude={"location", "open_roles"}),
        open_roles=[r.model_dump() for r in body.open_roles],
        location=point_wkt(body.location),
        source="user",
        claimed_by_member_id=user.member_id,
    )
    session.add(startup)
    try:
        await session.flush()
    except IntegrityError as exc:  # two founders racing for the same domain
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Domain already listed") from exc
    session.add(StartupMember(startup_id=startup.id, member_id=user.member_id, title="Founder"))
    await record_event(
        session, "startup.created", actor_id=user.member_id, target_type="startup",
        target_id=startup.id, payload={"sector": startup.sector},
    )  # fmt: skip
    await session.commit()
    await session.refresh(startup)
    return await startup_out(session, startup)


@router.get("/{startup_id}", response_model=StartupOut)
async def get_startup(startup_id: uuid.UUID, user: BrowseUser, session: SessionDep):
    return await startup_out(session, await _get(session, startup_id))


@router.patch("/{startup_id}", response_model=StartupOut)
async def update_startup(
    startup_id: uuid.UUID, body: StartupUpdate, user: CurrentUserDep, session: SessionDep
):
    startup = await _get(session, startup_id)
    _require_claimer(startup, user)
    changes = body.model_dump(exclude_unset=True)
    if "location" in changes:
        startup.location = point_wkt(body.location) if body.location else None
        changes.pop("location")
    if "open_roles" in changes:
        startup.open_roles = [r.model_dump() for r in body.open_roles or []]
        changes.pop("open_roles")
    for field, value in changes.items():
        setattr(startup, field, value)
    await record_event(
        session, "startup.updated", actor_id=user.member_id, target_type="startup",
        target_id=startup.id, payload={"fields": sorted(body.model_dump(exclude_unset=True))},
    )  # fmt: skip
    await session.commit()
    await session.refresh(startup)
    return await startup_out(session, startup)


@router.delete("/{startup_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_startup(startup_id: uuid.UUID, user: CurrentUserDep, session: SessionDep):
    """Founders can delete startups they added. Seeded/crawled ones can only be unlisted
    by an admin (not in the MVP), because they would be re-imported anyway."""
    startup = await _get(session, startup_id)
    _require_claimer(startup, user)
    if startup.source != "user":
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="Only startups you added can be deleted"
        )
    await session.execute(
        Need.__table__.delete().where(Need.owner_type == "startup", Need.owner_id == startup.id)
    )
    await session.delete(startup)
    await record_event(
        session,
        "startup.deleted",
        actor_id=user.member_id,
        target_type="startup",
        target_id=startup_id,
    )
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{startup_id}/needs", response_model=NeedOut, status_code=status.HTTP_201_CREATED)
async def add_startup_need(
    startup_id: uuid.UUID, body: NeedIn, user: CurrentUserDep, session: SessionDep
) -> Need:
    startup = await _get(session, startup_id)
    _require_claimer(startup, user)
    need = Need(
        owner_type="startup", owner_id=startup.id, capability_id=body.capability_id, text=body.text
    )
    session.add(need)
    await session.flush()
    await record_event(
        session, "need.created", actor_id=user.member_id, target_type="need", target_id=need.id,
        payload={"capability_id": need.capability_id, "owner_type": "startup"},
    )  # fmt: skip
    await session.commit()
    await session.refresh(need)
    return need
