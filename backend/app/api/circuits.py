"""Exchange circuits (F6).

- GET  /api/circuits/me               your loop cards, newest first
- POST /api/circuits/{id}/accept      accept the leg where you give help
- POST /api/circuits/{id}/decline     decline it (the whole circuit is called off)
- POST /api/circuits/{id}/rate        once active: you got your help, rate it 1-5
- POST /api/admin/circuits/run        "Run round now" (admins); ?dry_run=true previews
"""

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select

from app.auth import CurrentUser, CurrentUserDep, SessionDep, SettingsDep, require_admin
from app.circuits.service import run_round
from app.events import record_event
from app.models import Capability, Circuit, CircuitLeg, Member
from app.schemas import (
    CapabilityRef,
    CircuitCard,
    CircuitLegOut,
    CircuitRatingIn,
    MemberSummary,
    RoundCircuit,
    RoundOut,
)

router = APIRouter(prefix="/api", tags=["circuits"])
AdminUser = Annotated[CurrentUser, Depends(require_admin())]


def _lower_first(name: str) -> str:
    """'Marketing' -> 'marketing', but keep acronyms like 'UX research' or 'B2B sales'."""
    if len(name) > 1 and name[1].isupper():
        return name
    return name[:1].lower() + name[1:]


Step = tuple[uuid.UUID, uuid.UUID, str]  # giver, receiver, capability id


def loop_sentence(steps: list[Step], names: dict, caps: dict, me: uuid.UUID | None = None) -> str:
    """'You help Arjun with hiring, Arjun helps Priya with fundraising, Priya helps you
    with marketing.' Steps in loop order (starting with yours, if me is given)."""

    def who(member_id, start):
        if member_id == me:
            return "You" if start else "you"
        return names[member_id]

    parts = []
    for giver, receiver, cap in steps:
        verb = "help" if giver == me else "helps"
        parts.append(
            f"{who(giver, True)} {verb} {who(receiver, False)} with {_lower_first(caps[cap])}"
        )
    return ", ".join(parts) + "."


async def _people_and_caps(session, steps: list[Step]) -> tuple[dict, dict]:
    ids = {i for giver, receiver, _ in steps for i in (giver, receiver)}
    people = {
        m.id: m for m in (await session.scalars(select(Member).where(Member.id.in_(ids)))).all()
    }
    cap_ids = {cap for _, _, cap in steps}
    rows = await session.execute(
        select(Capability.id, Capability.name).where(Capability.id.in_(cap_ids))
    )
    return people, dict(rows.all())


def _steps(legs) -> list[Step]:
    """CircuitLeg rows or engine Edges -> (giver, receiver, capability) steps."""
    return [
        (leg.giver_id, leg.receiver_id, leg.capability_id)
        if isinstance(leg, CircuitLeg) else (leg.giver, leg.receiver, leg.capability_id)
        for leg in legs
    ]  # fmt: skip


def _actions(circuit: Circuit, legs: list[CircuitLeg], me: uuid.UUID, now: datetime) -> list[str]:
    mine = next(leg for leg in legs if leg.giver_id == me)
    incoming = next(leg for leg in legs if leg.receiver_id == me)
    if circuit.status == "proposed" and circuit.expires_at > now and mine.consent == "pending":
        return ["accept", "decline"]
    if circuit.status == "active" and not incoming.fulfilled:
        return ["rate"]
    return []


async def _cards(session, circuits: list[Circuit], me: uuid.UUID) -> list[CircuitCard]:
    if not circuits:
        return []
    legs_by_circuit: dict[uuid.UUID, list[CircuitLeg]] = {}
    all_legs = (
        await session.scalars(
            select(CircuitLeg)
            .where(CircuitLeg.circuit_id.in_([c.id for c in circuits]))
            .order_by(CircuitLeg.circuit_id, CircuitLeg.position)
        )
    ).all()
    for leg in all_legs:
        legs_by_circuit.setdefault(leg.circuit_id, []).append(leg)
    people, caps = await _people_and_caps(session, _steps(all_legs))
    names = {i: m.display_name for i, m in people.items()}
    now = datetime.now(UTC)
    cards = []
    for c in circuits:
        legs = legs_by_circuit[c.id]
        start = next(i for i, leg in enumerate(legs) if leg.giver_id == me)
        legs = legs[start:] + legs[:start]  # your leg first
        cards.append(
            CircuitCard(
                id=c.id,
                round_key=c.round_key,
                status=c.status,
                score=round(c.score * 100),
                created_at=c.created_at,
                expires_at=c.expires_at,
                sentence=loop_sentence(_steps(legs), names, caps, me),
                legs=[
                    CircuitLegOut(
                        position=leg.position,
                        giver=MemberSummary.model_validate(people[leg.giver_id]),
                        receiver=MemberSummary.model_validate(people[leg.receiver_id]),
                        capability=CapabilityRef(
                            id=leg.capability_id, name=caps[leg.capability_id]
                        ),
                        consent=leg.consent,
                        fulfilled=leg.fulfilled,
                        rating=leg.rating,
                    )
                    for leg in legs
                ],
                my_consent=legs[0].consent,
                actions=_actions(c, legs, me, now),
            )
        )
    return cards


async def _circuit_for(session, circuit_id: uuid.UUID, me: uuid.UUID):
    """The circuit (locked) and its legs, if me is in it."""
    circuit = await session.get(Circuit, circuit_id, with_for_update=True)
    legs = []
    if circuit is not None:
        legs = (
            await session.scalars(
                select(CircuitLeg).where(CircuitLeg.circuit_id == circuit.id)
                .order_by(CircuitLeg.position).with_for_update()
            )
        ).all()  # fmt: skip
    if circuit is None or me not in {leg.giver_id for leg in legs}:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Circuit not found")
    return circuit, list(legs)


async def _answer(session, circuit_id, me, accept: bool) -> CircuitCard:
    circuit, legs = await _circuit_for(session, circuit_id, me)
    now = datetime.now(UTC)
    if circuit.status == "proposed" and circuit.expires_at <= now:
        circuit.status = "expired"
        await record_event(session, "circuit.expired", actor_id=None, target_type="circuit",
                           target_id=circuit.id)  # fmt: skip
        await session.commit()
        raise HTTPException(status.HTTP_409_CONFLICT, detail="This circuit has expired")
    mine = next(leg for leg in legs if leg.giver_id == me)
    if circuit.status != "proposed" or mine.consent != "pending":
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail=f"Already answered (the circuit is {circuit.status})"
        )
    mine.consent, mine.consented_at = ("accepted" if accept else "declined"), now
    payload = {"score": round(circuit.score, 3)}
    await record_event(
        session, "circuit.accepted" if accept else "circuit.declined", actor_id=me,
        target_type="circuit", target_id=circuit.id, payload=payload,
    )  # fmt: skip
    if not accept:
        circuit.status = "declined"
    elif all(leg.consent == "accepted" for leg in legs):
        circuit.status = "active"
        await record_event(session, "circuit.activated", actor_id=None, target_type="circuit",
                           target_id=circuit.id, payload=payload)  # fmt: skip
    await session.commit()
    return (await _cards(session, [circuit], me))[0]


# --- member endpoints ---------------------------------------------------------------------


@router.get("/circuits/me", response_model=list[CircuitCard])
async def my_circuits(user: CurrentUserDep, session: SessionDep) -> list[CircuitCard]:
    """Your loop cards, newest first."""
    circuits = (
        await session.scalars(
            select(Circuit)
            .where(
                Circuit.id.in_(
                    select(CircuitLeg.circuit_id).where(CircuitLeg.giver_id == user.member_id)
                )
            )
            .order_by(Circuit.created_at.desc())
            .limit(50)
        )
    ).all()
    return await _cards(session, list(circuits), user.member_id)


@router.post("/circuits/{circuit_id}/accept", response_model=CircuitCard)
async def accept(circuit_id: uuid.UUID, user: CurrentUserDep, session: SessionDep):
    """Accept the leg where you give help. When all three accept, the circuit is active."""
    return await _answer(session, circuit_id, user.member_id, accept=True)


@router.post("/circuits/{circuit_id}/decline", response_model=CircuitCard)
async def decline(circuit_id: uuid.UUID, user: CurrentUserDep, session: SessionDep):
    """Decline: the circuit is called off for all three (no reason needed)."""
    return await _answer(session, circuit_id, user.member_id, accept=False)


@router.post("/circuits/{circuit_id}/rate", response_model=CircuitCard)
async def rate(
    circuit_id: uuid.UUID, body: CircuitRatingIn, user: CurrentUserDep, session: SessionDep
) -> CircuitCard:
    """You got the help you were promised: rate it. All three rated -> completed."""
    circuit, legs = await _circuit_for(session, circuit_id, user.member_id)
    incoming = next(leg for leg in legs if leg.receiver_id == user.member_id)
    if circuit.status != "active" or incoming.fulfilled:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="You can rate once the circuit is active, and only once",
        )
    incoming.fulfilled, incoming.rating = True, body.rating
    await record_event(
        session, "circuit.leg_rated", actor_id=user.member_id, target_type="circuit",
        target_id=circuit.id, payload={"rating": body.rating, "capability": incoming.capability_id},
    )  # fmt: skip
    if all(leg.fulfilled for leg in legs):
        circuit.status = "completed"
        await record_event(session, "circuit.completed", actor_id=None, target_type="circuit",
                           target_id=circuit.id)  # fmt: skip
    await session.commit()
    return (await _cards(session, [circuit], user.member_id))[0]


# --- admin --------------------------------------------------------------------------------


@router.post("/admin/circuits/run", response_model=RoundOut)
async def run_round_now(
    admin: AdminUser,
    session: SessionDep,
    settings: SettingsDep,
    dry_run: Annotated[bool, Query(description="Find and choose loops but save nothing")] = False,
) -> RoundOut:
    """'Run round now' for demos: the same round the weekly job runs."""
    result = await run_round(session, settings, actor_id=admin.member_id, dry_run=dry_run)
    await session.commit()
    people, caps = await _people_and_caps(
        session, _steps([leg for cycle in result.chosen for leg in cycle.legs])
    )
    names = {i: m.display_name for i, m in people.items()}
    ids = result.circuit_ids or [None] * len(result.chosen)
    return RoundOut(
        round_key=result.round_key,
        dry_run=dry_run,
        pool=result.pool,
        edges=result.edges,
        cycles_found=result.cycles_found,
        circuits=[
            RoundCircuit(
                id=circuit_id,
                score=round(cycle.score * 100),
                members=[MemberSummary.model_validate(people[m]) for m in cycle.members],
                sentence=loop_sentence(_steps(cycle.legs), names, caps),
            )
            for circuit_id, cycle in zip(ids, result.chosen, strict=True)
        ],
    )
