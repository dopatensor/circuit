"""Warm intros (F5): the best path to someone, weekly capacity, polite refusals.

A request travels sender -> mutual -> target when someone within two hops knows you
both, otherwise sender -> target. Everyone has a weekly capacity
(members.open_intro_slots) that covers requests they receive and requests they are
asked to pass on; senders also have a weekly sending limit (INTRO_REQUESTS_PER_WEEK).

The pure functions here (capacity maths, choosing a mutual, sentences) are unit-tested
on their own; the async ones read the database.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, func, or_, select, update

from app.events import record_event
from app.graph import Tie, get_graph
from app.models import IntroRequest, MatchResult, Member

WEEK = timedelta(days=7)
OPEN_STATUSES = ("pending", "forwarded")

# How two people know each other, as a few words for the UI.
TIE_LABEL = {
    "mentored": "mentorship",
    "worked_together": "worked together",
    "cohort": "same cohort",
    "invested": "investor relationship",
    "classmates": "classmates",
    "incubator": "same incubator",
    "intro": "met through an intro",
}


# --- pure helpers -------------------------------------------------------------------------


@dataclass(frozen=True)
class Load:
    """How much of someone's weekly capacity is taken."""

    slots: int
    recent: tuple[datetime, ...]  # when each counted request was made (last 7 days)

    @property
    def used(self) -> int:
        return len(self.recent)

    @property
    def full(self) -> bool:
        return self.used >= self.slots

    def next_free_at(self) -> datetime | None:
        """When a slot frees up: the oldest request that keeps them full turns 7 days old."""
        if not self.full or self.slots == 0:
            return None
        return sorted(self.recent)[self.used - self.slots] + WEEK


@dataclass(frozen=True)
class Mutual:
    member_id: uuid.UUID
    to_me: Tie
    to_target: Tie
    verification_level: int
    load: Load

    @property
    def weakest(self) -> float:
        return min(self.to_me.strength, self.to_target.strength)


def rank_mutuals(mutuals: list[Mutual]) -> list[Mutual]:
    """Best first: has room this week, then the strongest weakest tie, then the most
    trusted (verification level)."""
    return sorted(
        mutuals,
        key=lambda m: (m.load.full, -m.weakest, -m.verification_level, str(m.member_id)),
    )


def tie_label(tie: Tie) -> str:
    return TIE_LABEL.get(tie.source, tie.source.replace("_", " "))


def path_sentence(kind: str, target_name: str, via_name: str | None, ties: list[Tie]) -> str:
    if kind == "mutual" and via_name:
        return (
            f"{via_name} knows you both ({tie_label(ties[0])} with you; "
            f"{tie_label(ties[1])} with {target_name}). Your request goes to them first."
        )
    if kind == "direct":
        return (
            f"You already know {target_name} ({tie_label(ties[0])}), "
            "so your request goes straight to them."
        )
    return f"No mutual connection yet, so your request goes straight to {target_name}."


def day(when: datetime) -> str:
    return f"{when:%a} {when.day} {when:%b}"  # e.g. "Tue 13 Oct" (no leading zero)


def busy_message(name: str, load: Load, *, as_mutual: bool = False) -> str:
    if load.slots == 0:
        return f"{name} isn't taking intro requests right now. Try one of your other matches."
    who = f"{name}, who knows you both," if as_mutual else name
    return (
        f"{who} has had a busy week of intro requests. They'll have room again from "
        f"{day(load.next_free_at())}, so please try then."
    )


def sender_limit_message(limit: int, load: Load) -> str:
    return (
        f"You've sent {limit} intro requests this week, which is the weekly limit. "
        f"You can send more from {day(load.next_free_at())}."
    )


# --- database helpers ---------------------------------------------------------------------


def _counts_for(member_ids):
    """Requests that use up a member's weekly capacity: ones they received (unless a
    mutual declined them before they arrived) and ones they were asked to pass on."""
    received = and_(
        IntroRequest.to_member.in_(member_ids),
        ~and_(
            IntroRequest.status == "declined",
            IntroRequest.via_member.is_not(None),
            IntroRequest.forwarded_at.is_(None),
        ),
    )
    return or_(received, IntroRequest.via_member.in_(member_ids))


async def loads(session, members: list[Member], now: datetime | None = None) -> dict:
    """{member_id: Load} for the last 7 days."""
    now = now or datetime.now(UTC)
    ids = [m.id for m in members]
    out = {m.id: [] for m in members}
    if not ids:
        return {}
    rows = await session.execute(
        select(IntroRequest.to_member, IntroRequest.via_member, IntroRequest.created_at).where(
            IntroRequest.created_at > now - WEEK,
            IntroRequest.status != "withdrawn",
            _counts_for(ids),
        )
    )
    for to_member, via_member, created in rows:
        for mid in {to_member, via_member} & out.keys():
            out[mid].append(created)
    return {m.id: Load(m.open_intro_slots, tuple(out[m.id])) for m in members}


async def sender_load(session, member_id: uuid.UUID, limit: int, now=None) -> Load:
    now = now or datetime.now(UTC)
    rows = await session.scalars(
        select(IntroRequest.created_at).where(
            IntroRequest.from_member == member_id, IntroRequest.created_at > now - WEEK
        )
    )
    return Load(limit, tuple(rows.all()))


@dataclass
class PathPlan:
    kind: str  # mutual | direct | none
    target: Member
    mutuals: list[Mutual]  # ranked; the first is the one we would use
    direct_tie: Tie | None
    members: dict[uuid.UUID, Member]

    @property
    def via(self) -> Mutual | None:
        return self.mutuals[0] if self.kind == "mutual" else None


async def plan_path(session, me: uuid.UUID, target: Member) -> PathPlan:
    """Find the best way to reach target: through a mutual (recursive SQL, 1-2 hops)."""
    graph = get_graph()
    paths = await graph.paths(session, me, target.id, max_hops=2)
    direct = any(len(p.members) == 2 for p in paths)
    mutual_ids = [p.members[1] for p in paths if len(p.members) == 3]
    ties = await graph.ties(
        session,
        [(me, target.id)] + [(me, m) for m in mutual_ids] + [(m, target.id) for m in mutual_ids],
    )
    members = {
        m.id: m
        for m in (await session.scalars(select(Member).where(Member.id.in_(mutual_ids)))).all()
    }
    member_loads = await loads(session, list(members.values()))
    mutuals = rank_mutuals(
        [
            Mutual(
                mid,
                ties[frozenset((me, mid))],
                ties[frozenset((mid, target.id))],
                members[mid].verification_level,
                member_loads[mid],
            )
            for mid in mutual_ids
            if mid in members
        ]
    )
    # Already connected: no mutual needed. Otherwise the best mutual, if any.
    kind = "direct" if direct else ("mutual" if mutuals else "none")
    return PathPlan(kind, target, mutuals, ties.get(frozenset((me, target.id))), members)


async def match_is_bridge(session, me: Member, target: Member) -> bool:
    """Use the precomputed match's Bridge flag; fall back to comparing sectors."""
    flag = await session.scalar(
        select(MatchResult.is_bridge).where(
            MatchResult.member_id == me.id,
            MatchResult.candidate_type == "member",
            MatchResult.candidate_id == target.id,
        )
    )
    if flag is not None:
        return flag
    return bool(me.sector and target.sector and me.sector != target.sector)


async def open_request(session, sender: uuid.UUID, target: uuid.UUID) -> uuid.UUID | None:
    return await session.scalar(
        select(IntroRequest.id).where(
            IntroRequest.from_member == sender,
            IntroRequest.to_member == target,
            IntroRequest.status.in_(OPEN_STATUSES),
        )
    )


async def expire_stale(session, expiry_days: int, now: datetime | None = None) -> int:
    """Mark requests nobody answered within expiry_days as expired (scheduled job)."""
    now = now or datetime.now(UTC)
    ids = (
        await session.scalars(
            update(IntroRequest)
            .where(
                IntroRequest.status.in_(OPEN_STATUSES),
                func.coalesce(IntroRequest.forwarded_at, IntroRequest.created_at)
                < now - timedelta(days=expiry_days),
            )
            .values(status="expired", responded_at=now)
            .returning(IntroRequest.id)
        )
    ).all()
    for intro_id in ids:
        await record_event(
            session, "intro.expired", actor_id=None, target_type="intro", target_id=intro_id
        )
    return len(ids)
