"""Startup profiles. Anyone verified can browse; only the claimer can edit."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError

from app import claims
from app.auth import (
    LEVEL_BROWSE,
    CurrentUser,
    CurrentUserDep,
    SessionDep,
    SettingsDep,
    require_level,
)
from app.events import record_event
from app.models import Event, Member, Need, Startup, StartupClaim, StartupMember
from app.profiles import point_wkt, startup_out
from app.schemas import (
    ClaimStartIn,
    ClaimStartOut,
    ClaimVerifyIn,
    InterestOut,
    MemberSummary,
    NeedIn,
    NeedOut,
    Page,
    StartupCreate,
    StartupOut,
    StartupStats,
    StartupUpdate,
)

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


VIEW_DEDUPE = timedelta(hours=24)


async def _on_team(session, startup_id: uuid.UUID, member_id: uuid.UUID) -> bool:
    return bool(
        await session.scalar(
            select(StartupMember.member_id).where(
                StartupMember.startup_id == startup_id, StartupMember.member_id == member_id
            )
        )
    )


@router.get("/{startup_id}", response_model=StartupOut)
async def get_startup(startup_id: uuid.UUID, user: BrowseUser, session: SessionDep):
    """A startup's page. Opening it counts as a view (once per person per 24 hours;
    the startup's own team doesn't count)."""
    startup = await _get(session, startup_id)
    if startup.claimed_by_member_id != user.member_id and not await _on_team(
        session, startup.id, user.member_id
    ):
        seen_recently = await session.scalar(
            select(Event.id).where(
                Event.type == "startup.viewed",
                Event.target_type == "startup",
                Event.target_id == str(startup.id),
                Event.actor_id == user.member_id,
                Event.created_at > datetime.now(UTC) - VIEW_DEDUPE,
            )
        )
        if not seen_recently:
            # One atomic UPDATE, so simultaneous views are all counted.
            await session.execute(
                update(Startup)
                .where(Startup.id == startup.id)
                .values(view_count=Startup.view_count + 1)
            )
            await record_event(
                session, "startup.viewed", actor_id=user.member_id, target_type="startup",
                target_id=startup.id, payload={"actor_role": user.role},
            )  # fmt: skip
            await session.commit()
            await session.refresh(startup)
    return await startup_out(session, startup)


def _interest_filter(startup_id: uuid.UUID):
    return (
        Event.type == "startup.interest",
        Event.target_type == "startup",
        Event.target_id == str(startup_id),
    )


async def _interest_count(session, startup_id: uuid.UUID) -> int:
    return await session.scalar(
        select(func.count(func.distinct(Event.actor_id))).where(*_interest_filter(startup_id))
    )


@router.post("/{startup_id}/interest", response_model=InterestOut)
async def express_interest(startup_id: uuid.UUID, user: BrowseUser, session: SessionDep):
    """The "I'm interested" button. Pressing it again changes nothing."""
    startup = await _get(session, startup_id)
    already = await session.scalar(
        select(Event.id).where(*_interest_filter(startup.id), Event.actor_id == user.member_id)
    )
    if not already:
        await record_event(
            session, "startup.interest", actor_id=user.member_id, target_type="startup",
            target_id=startup.id, payload={"actor_role": user.role},
        )  # fmt: skip
        await session.commit()
    return InterestOut(interested=True, interest_count=await _interest_count(session, startup.id))


@router.get("/{startup_id}/stats", response_model=StartupStats)
async def startup_stats(startup_id: uuid.UUID, user: BrowseUser, session: SessionDep):
    """Visible to everyone, including on unclaimed startups: it's what motivates a
    founder to claim their page."""
    startup = await _get(session, startup_id)
    student = Member.role == "student"
    viewers = await session.scalar(
        select(func.count(func.distinct(Event.actor_id)))
        .join(Member, Member.id == Event.actor_id)
        .where(
            Event.type == "startup.viewed",
            Event.target_type == "startup",
            Event.target_id == str(startup.id),
            Event.created_at > datetime.now(UTC) - timedelta(days=30),
            student,
        )
    )
    interested_students = await session.scalar(
        select(func.count(func.distinct(Event.actor_id)))
        .join(Member, Member.id == Event.actor_id)
        .where(*_interest_filter(startup.id), student)
    )
    return StartupStats(
        view_count=startup.view_count,
        student_viewers_30d=viewers or 0,
        interested_students=interested_students or 0,
        interested_total=await _interest_count(session, startup.id),
    )


@router.get("/{startup_id}/interested", response_model=list[MemberSummary])
async def interested_people(startup_id: uuid.UUID, user: CurrentUserDep, session: SessionDep):
    """Who pressed "I'm interested". Only for the founder who claimed the startup."""
    startup = await _get(session, startup_id)
    _require_claimer(startup, user)
    members = await session.scalars(
        select(Member)
        .where(Member.id.in_(select(Event.actor_id).where(*_interest_filter(startup.id))))
        .order_by(Member.display_name)
    )
    return [MemberSummary.model_validate(m) for m in members]


@router.post(
    "/{startup_id}/claim", response_model=ClaimStartOut, status_code=status.HTTP_201_CREATED
)
async def start_claim(
    startup_id: uuid.UUID,
    body: ClaimStartIn,
    user: BrowseUser,
    session: SessionDep,
    settings: SettingsDep,
) -> ClaimStartOut:
    """Step 1 of claiming: give an email address on the startup's own domain. We send
    a 6-digit code there (simulated in development: the code comes back as dev_code)."""
    startup = await _get(session, startup_id)
    if user.role != "founder":
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Only founders can claim startups")
    if startup.claimed_by_member_id is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="This startup is already claimed")
    domain = claims.email_domain(body.email)
    if domain is None or not claims.domain_matches(domain, startup.website_domain):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Use an email address at {startup.website_domain}",
        )
    # Only the newest code works.
    await session.execute(
        update(StartupClaim)
        .where(
            StartupClaim.startup_id == startup.id,
            StartupClaim.member_id == user.member_id,
            StartupClaim.status == "pending",
        )
        .values(status="superseded")
    )
    claim = StartupClaim(
        id=uuid.uuid4(),
        startup_id=startup.id,
        member_id=user.member_id,
        email_domain=domain,
        expires_at=claims.expires_at(),
        code_hash="",
    )
    code = claims.new_code()
    claim.code_hash = claims.hash_code(claim.id, code)
    try:
        shown = claims.send_claim_code(settings, body.email, startup.name, code)
    except claims.EmailNotConfigured as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, detail="Email delivery is not configured yet"
        ) from exc
    session.add(claim)
    await record_event(
        session, "startup.claim_started", actor_id=user.member_id, target_type="startup",
        target_id=startup.id, payload={"claim_id": str(claim.id)},
    )  # fmt: skip
    await session.commit()
    return ClaimStartOut(
        claim_id=claim.id, sent_to_domain=domain, expires_at=claim.expires_at, dev_code=shown
    )


@router.post("/{startup_id}/claim/verify", response_model=StartupOut)
async def verify_claim(
    startup_id: uuid.UUID, body: ClaimVerifyIn, user: BrowseUser, session: SessionDep
) -> StartupOut:
    """Step 2: enter the code. On success the startup is yours to edit."""
    startup = await _get(session, startup_id)
    claim = await session.get(StartupClaim, body.claim_id)
    if (
        claim is None
        or claim.startup_id != startup.id
        or claim.member_id != user.member_id
        or claim.status != "pending"
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No pending claim; start again")
    if claim.expires_at < datetime.now(UTC) or claim.attempts >= claims.MAX_ATTEMPTS:
        claim.status = "expired"
        await session.commit()
        raise HTTPException(status.HTTP_410_GONE, detail="This code has expired; start again")
    if not claims.code_matches(claim.id, body.code, claim.code_hash):
        claim.attempts += 1
        if claim.attempts >= claims.MAX_ATTEMPTS:
            claim.status = "expired"
        await record_event(
            session, "startup.claim_failed", actor_id=user.member_id, target_type="startup",
            target_id=startup.id, payload={"attempts": claim.attempts},
        )  # fmt: skip
        await session.commit()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Wrong code")

    # Claim only if still unclaimed (two founders racing: the first one wins).
    result = await session.execute(
        update(Startup)
        .where(Startup.id == startup.id, Startup.claimed_by_member_id.is_(None))
        .values(claimed_by_member_id=user.member_id)
    )
    if result.rowcount == 0:
        claim.status = "superseded"
        await session.commit()
        raise HTTPException(status.HTTP_409_CONFLICT, detail="This startup is already claimed")
    claim.status = "verified"
    claim.verified_at = datetime.now(UTC)
    if not await _on_team(session, startup.id, user.member_id):
        session.add(StartupMember(startup_id=startup.id, member_id=user.member_id, title="Founder"))
    await record_event(
        session, "startup.claimed", actor_id=user.member_id, target_type="startup",
        target_id=startup.id, payload={"email_domain": claim.email_domain},
    )  # fmt: skip
    await session.commit()
    await session.refresh(startup)
    return await startup_out(session, startup)


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
