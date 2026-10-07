"""Warm intros (F5).

- GET  /api/intros/path/{member_id}  how a request would travel (level 2, like matches)
- POST /api/intros                   ask for an intro (level 3); goes via the best mutual
- GET  /api/intros/me                sent, waiting for you to pass on, received, capacity
- POST /api/intros/{id}/forward      the mutual passes it on
- POST /api/intros/{id}/accept       the target accepts (they become connected)
- POST /api/intros/{id}/decline      the mutual or the target says no
- POST /api/intros/{id}/withdraw     the sender takes it back
- POST /api/intros/{id}/rate         the sender rates how it went (1-5)

Requests beyond someone's weekly capacity are refused with 429 and a polite message.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select

from app.auth import (
    LEVEL_INTROS,
    LEVEL_MATCHES,
    CurrentUser,
    CurrentUserDep,
    SessionDep,
    SettingsDep,
    require_level,
)
from app.events import record_event
from app.graph import get_graph
from app.intros import (
    OPEN_STATUSES,
    busy_message,
    loads,
    match_is_bridge,
    open_request,
    path_sentence,
    plan_path,
    sender_limit_message,
)
from app.intros import sender_load as get_sender_load
from app.models import IntroRequest, Member
from app.schemas import (
    Capacity,
    IntroInbox,
    IntroOut,
    IntroPath,
    IntroRatingIn,
    IntroRequestIn,
    MemberSummary,
)

router = APIRouter(prefix="/api/intros", tags=["intros"])
MatchUser = Annotated[CurrentUser, Depends(require_level(LEVEL_MATCHES))]
IntroUser = Annotated[CurrentUser, Depends(require_level(LEVEL_INTROS))]

NEW_TIE_STRENGTH = 0.5  # an accepted intro connects the two people
WHO_CAN = {  # action -> roles allowed to take it
    "forward": ("mutual",),
    "accept": ("target",),
    "decline": ("mutual", "target"),
    "withdraw": ("sender",),
    "rate": ("sender",),
}


class Refusal(Exception):
    def __init__(self, code: int, message: str, retry_at: datetime | None = None):
        self.code, self.message, self.retry_at = code, message, retry_at

    def http(self) -> HTTPException:
        headers = None
        if self.retry_at:
            seconds = max(int((self.retry_at - datetime.now(UTC)).total_seconds()), 1)
            headers = {"Retry-After": str(seconds)}
        return HTTPException(self.code, detail=self.message, headers=headers)


# --- helpers ------------------------------------------------------------------------------


async def _member_or_404(session, member_id: uuid.UUID) -> Member:
    member = await session.get(Member, member_id)
    if member is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Member not found")
    return member


async def _check(session, settings, user: CurrentUser, me: Member, plan, via_id=None):
    """Everything that would stop this request, in the order a person would want to
    hear it. Returns the mutual to use (or None for a direct request)."""
    target = plan.target
    if target.id == me.id:
        raise Refusal(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "You can't ask for an intro to yourself"
        )
    if user.verification_level < LEVEL_INTROS:
        raise Refusal(
            status.HTTP_403_FORBIDDEN,
            f"Intro requests need verification level {LEVEL_INTROS} "
            f"(you have {user.verification_level}). An admin verifies your role.",
        )
    if await open_request(session, me.id, target.id):
        raise Refusal(
            status.HTTP_409_CONFLICT, f"You already have an open request to {target.display_name}"
        )
    sent = await get_sender_load(session, me.id, settings.intro_requests_per_week)
    if sent.full:
        raise Refusal(
            status.HTTP_429_TOO_MANY_REQUESTS,
            sender_limit_message(settings.intro_requests_per_week, sent),
            sent.next_free_at(),
        )
    target_load = (await loads(session, [target]))[target.id]
    if target_load.full:
        raise Refusal(
            status.HTTP_429_TOO_MANY_REQUESTS,
            busy_message(target.display_name, target_load),
            target_load.next_free_at(),
        )
    if plan.kind != "mutual":
        if via_id is not None:
            raise Refusal(
                status.HTTP_422_UNPROCESSABLE_CONTENT, "That person doesn't know you both"
            )
        return None
    if via_id is None:
        via = plan.mutuals[0]
    else:
        via = next((m for m in plan.mutuals if m.member_id == via_id), None)
        if via is None:
            raise Refusal(
                status.HTTP_422_UNPROCESSABLE_CONTENT, "That person doesn't know you both"
            )
    if via.load.full:  # ranked first means every mutual is full
        name = plan.members[via.member_id].display_name
        raise Refusal(
            status.HTTP_429_TOO_MANY_REQUESTS,
            busy_message(name, via.load, as_mutual=True),
            via.load.next_free_at(),
        )
    return via


def _summary(m: Member) -> MemberSummary:
    return MemberSummary.model_validate(m)


def _role_and_actions(intro: IntroRequest, me: uuid.UUID) -> tuple[str, list[str]]:
    s = intro.status
    if intro.from_member == me:
        actions = ["withdraw"] if s in OPEN_STATUSES else ["rate"] if s == "accepted" else []
        return "sender", actions
    if intro.via_member == me and intro.to_member != me:
        return "mutual", ["forward", "decline"] if s == "pending" else []
    waiting_for_target = s == "forwarded" or (s == "pending" and intro.via_member is None)
    return "target", ["accept", "decline"] if waiting_for_target else []


async def _out(session, intros: list[IntroRequest], me: uuid.UUID) -> list[IntroOut]:
    ids = {i for x in intros for i in (x.from_member, x.to_member, x.via_member) if i}
    people = {
        m.id: m for m in (await session.scalars(select(Member).where(Member.id.in_(ids)))).all()
    }
    out = []
    for x in intros:
        role, actions = _role_and_actions(x, me)
        out.append(
            IntroOut(
                id=x.id,
                status=x.status,
                sender=_summary(people[x.from_member]),
                target=_summary(people[x.to_member]),
                via=_summary(people[x.via_member]) if x.via_member in people else None,
                reason=x.reason,
                is_bridge=x.is_bridge,
                outcome_rating=x.outcome_rating,
                created_at=x.created_at,
                forwarded_at=x.forwarded_at,
                responded_at=x.responded_at,
                completed_at=x.completed_at,
                my_role=role,
                actions=actions,
            )
        )
    return out


async def _intro_for_action(session, settings, intro_id: uuid.UUID, me: uuid.UUID, action: str):
    """The request, locked, if `me` may do `action` on it now; otherwise a clear error."""
    intro = await session.get(IntroRequest, intro_id, with_for_update=True)
    if intro is None or me not in (intro.from_member, intro.to_member, intro.via_member):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Intro request not found")
    role, actions = _role_and_actions(intro, me)
    if role == "target" and intro.via_member and intro.forwarded_at is None:
        # The target can't see a request the mutual hasn't passed on yet.
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Intro request not found")
    waited_since = intro.forwarded_at or intro.created_at
    if intro.status in OPEN_STATUSES and waited_since < datetime.now(UTC) - timedelta(
        days=settings.intro_expiry_days
    ):
        intro.status, intro.responded_at = "expired", datetime.now(UTC)
        await record_event(session, "intro.expired", actor_id=None, target_type="intro",
                           target_id=intro.id)  # fmt: skip
        await session.commit()
        raise HTTPException(status.HTTP_409_CONFLICT, detail="This request has expired")
    if role not in WHO_CAN[action]:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, detail=f"Only the {' or '.join(WHO_CAN[action])} can do that"
        )
    if action not in actions:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=f"You can't {action} this request (it is {intro.status})",
        )
    return intro, role


async def _done(session, intro, me, event: str, payload: dict | None = None) -> IntroOut:
    await record_event(
        session, event, actor_id=me, target_type="intro", target_id=intro.id,
        payload={"is_bridge": intro.is_bridge, "via": intro.via_member is not None,
                 **(payload or {})},
    )  # fmt: skip
    await session.commit()
    return (await _out(session, [intro], me))[0]


# --- endpoints ----------------------------------------------------------------------------


@router.get("/path/{member_id}", response_model=IntroPath)
async def intro_path(
    member_id: uuid.UUID, user: MatchUser, session: SessionDep, settings: SettingsDep
) -> IntroPath:
    """The best mutual connection to this person (1-2 hops), and whether you can ask now."""
    target = await _member_or_404(session, member_id)
    me = await session.get_one(Member, user.member_id)
    plan = await plan_path(session, me.id, target)
    blocked = None
    try:
        await _check(session, settings, user, me, plan)
    except Refusal as r:
        blocked = r.message
    via = plan.via
    ties = [via.to_me, via.to_target] if via else [plan.direct_tie] if plan.direct_tie else []
    await record_event(
        session, "intro.path_viewed", actor_id=me.id, target_type="member", target_id=target.id,
        payload={"kind": plan.kind, "mutuals": len(plan.mutuals)},
    )  # fmt: skip
    await session.commit()
    return IntroPath(
        target=_summary(target),
        kind=plan.kind,
        via=_summary(plan.members[via.member_id]) if via else None,
        strengths=[t.strength for t in ties],
        sentence=path_sentence(
            plan.kind,
            target.display_name,
            plan.members[via.member_id].display_name if via else None,
            ties,
        ),
        alternatives=[_summary(plan.members[m.member_id]) for m in plan.mutuals[1:4]],
        can_request=blocked is None,
        blocked_reason=blocked,
        open_request_id=await open_request(session, me.id, target.id),
    )


@router.post("", response_model=IntroOut, status_code=status.HTTP_201_CREATED)
async def request_intro(
    body: IntroRequestIn, user: IntroUser, session: SessionDep, settings: SettingsDep
) -> IntroOut:
    """Ask for an intro. It goes through the best mutual connection when there is one
    (or the mutual you pick from the path's alternatives), otherwise straight to them."""
    target = await _member_or_404(session, body.to_member_id)
    # Lock the people involved (in id order, so two requests can't deadlock) so that two
    # requests at once can't both squeeze into the last free slot.
    me = await session.get_one(Member, user.member_id)
    plan = await plan_path(session, me.id, target)
    lock_ids = sorted({me.id, target.id, *(m.member_id for m in plan.mutuals)})
    await session.execute(select(Member.id).where(Member.id.in_(lock_ids)).with_for_update())
    plan = await plan_path(session, me.id, target)  # loads again, now that nobody can race us
    try:
        via = await _check(session, settings, user, me, plan, body.via_member_id)
    except Refusal as r:
        if r.code == status.HTTP_429_TOO_MANY_REQUESTS:
            await record_event(
                session, "intro.refused", actor_id=me.id, target_type="member",
                target_id=target.id, payload={"why": "capacity"},
            )  # fmt: skip
            await session.commit()
        raise r.http() from None
    intro = IntroRequest(
        from_member=me.id,
        to_member=target.id,
        via_member=via.member_id if via else None,
        status="pending",
        reason=body.reason.strip(),
        is_bridge=await match_is_bridge(session, me, target),
    )
    session.add(intro)
    await session.flush()
    await session.refresh(intro)
    return await _done(session, intro, me.id, "intro.requested", {"path": plan.kind})


@router.get("/me", response_model=IntroInbox)
async def my_intros(user: CurrentUserDep, session: SessionDep, settings: SettingsDep):
    me = await session.get_one(Member, user.member_id)
    intros = (
        await session.scalars(
            select(IntroRequest)
            .where(
                or_(
                    IntroRequest.from_member == me.id,
                    IntroRequest.via_member == me.id,
                    IntroRequest.to_member == me.id,
                )
            )
            .order_by(IntroRequest.created_at.desc())
            .limit(200)
        )
    ).all()
    out = {o.id: o for o in await _out(session, list(intros), me.id)}
    sent, to_forward, received = [], [], []
    for x in intros:
        if x.from_member == me.id:
            sent.append(out[x.id])
        elif x.via_member == me.id:
            # Everything you were asked to pass on; open ones first.
            to_forward.append(out[x.id])
        elif x.via_member is None or x.forwarded_at is not None:
            received.append(out[x.id])
    to_forward.sort(key=lambda o: o.status != "pending")
    load = (await loads(session, [me]))[me.id]
    sent_load = await get_sender_load(session, me.id, settings.intro_requests_per_week)
    return IntroInbox(
        sent=sent,
        to_forward=to_forward,
        received=received,
        capacity=Capacity(slots=load.slots, used=load.used, next_free_at=load.next_free_at()),
        sent_this_week=sent_load.used,
        sent_limit=settings.intro_requests_per_week,
    )


@router.post("/{intro_id}/forward", response_model=IntroOut)
async def forward(intro_id: uuid.UUID, user: CurrentUserDep, session: SessionDep,
                  settings: SettingsDep) -> IntroOut:  # fmt: skip
    """The mutual passes the request on to the target."""
    intro, _ = await _intro_for_action(session, settings, intro_id, user.member_id, "forward")
    intro.status, intro.forwarded_at = "forwarded", datetime.now(UTC)
    return await _done(session, intro, user.member_id, "intro.forwarded")


@router.post("/{intro_id}/accept", response_model=IntroOut)
async def accept(intro_id: uuid.UUID, user: CurrentUserDep, session: SessionDep,
                 settings: SettingsDep) -> IntroOut:  # fmt: skip
    """The target accepts: the two are now connected."""
    intro, _ = await _intro_for_action(session, settings, intro_id, user.member_id, "accept")
    intro.status, intro.responded_at = "accepted", datetime.now(UTC)
    await get_graph().connect(
        session, intro.from_member, intro.to_member, NEW_TIE_STRENGTH, "intro"
    )
    return await _done(session, intro, user.member_id, "intro.accepted")


@router.post("/{intro_id}/decline", response_model=IntroOut)
async def decline(intro_id: uuid.UUID, user: CurrentUserDep, session: SessionDep,
                  settings: SettingsDep) -> IntroOut:  # fmt: skip
    """The mutual (before passing it on) or the target says no, kindly."""
    intro, role = await _intro_for_action(session, settings, intro_id, user.member_id, "decline")
    intro.status, intro.responded_at = "declined", datetime.now(UTC)
    return await _done(session, intro, user.member_id, "intro.declined", {"by": role})


@router.post("/{intro_id}/withdraw", response_model=IntroOut)
async def withdraw(intro_id: uuid.UUID, user: CurrentUserDep, session: SessionDep,
                   settings: SettingsDep) -> IntroOut:  # fmt: skip
    intro, _ = await _intro_for_action(session, settings, intro_id, user.member_id, "withdraw")
    intro.status, intro.responded_at = "withdrawn", datetime.now(UTC)
    return await _done(session, intro, user.member_id, "intro.withdrawn")


@router.post("/{intro_id}/rate", response_model=IntroOut)
async def rate(intro_id: uuid.UUID, body: IntroRatingIn, user: CurrentUserDep,
               session: SessionDep, settings: SettingsDep) -> IntroOut:  # fmt: skip
    """After an accepted intro, the sender rates how useful it was (1-5)."""
    intro, _ = await _intro_for_action(session, settings, intro_id, user.member_id, "rate")
    intro.status, intro.outcome_rating = "completed", body.rating
    intro.completed_at = datetime.now(UTC)
    return await _done(session, intro, user.member_id, "intro.rated", {"rating": body.rating})
