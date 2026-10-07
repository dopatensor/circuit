"""Warm intros (F5): paths, requests via a mutual, capacity, responses, events."""

import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_engine, make_engine
from app.graph import Tie
from app.intros import Load, Mutual, busy_message, expire_stale, path_sentence, rank_mutuals
from app.main import create_app
from app.models import Connection, Event
from app.seed.ids import member_id
from tests.conftest import make_test_settings

pytestmark = pytest.mark.anyio
REASON = "Raising pre-seed and would value your view on our model."
NOW = datetime(2026, 10, 7, 12, tzinfo=UTC)


# --- pure helpers -------------------------------------------------------------------------


def test_next_free_slot_is_when_the_oldest_blocking_request_turns_a_week_old():
    days = [NOW - timedelta(days=d) for d in (1, 5, 3)]
    assert Load(2, tuple(days)).next_free_at() == NOW - timedelta(days=3) + timedelta(days=7)
    assert Load(3, tuple(days)).next_free_at() == NOW - timedelta(days=5) + timedelta(days=7)
    assert Load(4, tuple(days)).next_free_at() is None and not Load(4, tuple(days)).full


def test_busy_messages_are_polite_and_give_a_date():
    load = Load(1, (datetime(2026, 10, 6, tzinfo=UTC),))
    msg = busy_message("Vikram Shah", load)
    assert "busy week" in msg and "Tue 13 Oct" in msg
    assert "isn't taking intro requests" in busy_message("Vikram Shah", Load(0, ()))
    assert "who knows you both" in busy_message("Lakshmi", load, as_mutual=True)


def test_mutuals_with_room_beat_stronger_ones_without():
    def mutual(strength, level=3, full=False):
        load = Load(1, (NOW,)) if full else Load(1, ())
        tie = Tie(strength, "cohort")
        return Mutual(uuid.uuid4(), tie, tie, level, load)

    busy_strong, weak, strong, strong_less_trusted = (
        mutual(0.9, full=True), mutual(0.4), mutual(0.8), mutual(0.8, level=2)
    )  # fmt: skip
    ranked = rank_mutuals([weak, busy_strong, strong_less_trusted, strong])
    assert ranked == [strong, strong_less_trusted, weak, busy_strong]


def test_path_sentences():
    ties = [Tie(0.9, "mentored"), Tie(0.9, "worked_together")]
    s = path_sentence("mutual", "Vikram Shah", "Dr. Lakshmi Narayan", ties)
    assert s.startswith("Dr. Lakshmi Narayan knows you both (mentorship with you;")
    assert "worked together with Vikram Shah" in s
    assert "already know" in path_sentence("direct", "Vikram", None, ties[:1])
    assert "No mutual connection" in path_sentence("none", "Vikram", None, [])


# --- fixtures -----------------------------------------------------------------------------


async def connect(session, a, b, strength=0.8, source="cohort"):
    session.add(Connection(member_a=min(a, b), member_b=max(a, b), strength=strength,
                           source=source))  # fmt: skip
    await session.commit()


@pytest.fixture
async def trio(make_member, session):
    """sender -- mutual -- target, all verified for intros; sender and target not connected."""
    sender = await make_member(role="founder", level=3, sector="climatetech")
    mutual = await make_member(role="mentor", level=3, sector="climatetech", open_intro_slots=3)
    target = await make_member(role="investor", level=3, sector="fintech", open_intro_slots=2)
    await connect(session, sender[0], mutual[0], 0.8, "mentored")
    await connect(session, mutual[0], target[0], 0.7, "worked_together")
    return sender, mutual, target


async def ask(client, sender, target, **extra):
    return await client.post(
        "/api/intros",
        headers=sender[1],
        json={"to_member_id": str(target[0]), "reason": REASON, **extra},
    )


async def inbox(client, who) -> dict:
    r = await client.get("/api/intros/me", headers=who[1])
    assert r.status_code == 200, r.text
    return r.json()


async def events_for(session, intro_id) -> list[Event]:
    return (
        await session.scalars(
            select(Event).where(Event.target_id == str(intro_id)).order_by(Event.id)
        )
    ).all()


# --- story 4 ------------------------------------------------------------------------------


async def test_story4_rohan_reaches_vikram_through_lakshmi(client, login):
    r = await client.get(f"/api/intros/path/{member_id('vikram')}", headers=await login("rohan"))
    assert r.status_code == 200, r.text
    path = r.json()
    assert path["kind"] == "mutual" and path["via"]["id"] == str(member_id("lakshmi"))
    assert path["strengths"] == [0.9, 0.9]
    assert path["can_request"] and path["blocked_reason"] is None
    assert "Dr. Lakshmi Narayan knows you both" in path["sentence"]


# --- the full flow through a mutual -------------------------------------------------------


async def test_request_goes_via_the_mutual_then_target_accepts_and_sender_rates(
    client, trio, session
):
    sender, mutual, target = trio
    path = (await client.get(f"/api/intros/path/{target[0]}", headers=sender[1])).json()
    assert path["kind"] == "mutual" and path["via"]["id"] == str(mutual[0])

    r = await ask(client, sender, target)
    assert r.status_code == 201, r.text
    intro = r.json()
    assert intro["status"] == "pending" and intro["via"]["id"] == str(mutual[0])
    assert intro["is_bridge"] is True  # climatetech -> fintech
    assert intro["my_role"] == "sender" and intro["actions"] == ["withdraw"]

    # The target doesn't see it, and can't act on it, until the mutual passes it on.
    assert (await inbox(client, target))["received"] == []
    r = await client.post(f"/api/intros/{intro['id']}/accept", headers=target[1])
    assert r.status_code == 404

    waiting = (await inbox(client, mutual))["to_forward"]
    assert [w["id"] for w in waiting] == [intro["id"]]
    assert waiting[0]["actions"] == ["forward", "decline"] and waiting[0]["reason"] == REASON

    r = await client.post(f"/api/intros/{intro['id']}/forward", headers=mutual[1])
    assert r.status_code == 200 and r.json()["status"] == "forwarded"

    received = (await inbox(client, target))["received"]
    assert received[0]["id"] == intro["id"] and received[0]["actions"] == ["accept", "decline"]
    r = await client.post(f"/api/intros/{intro['id']}/accept", headers=target[1])
    assert r.status_code == 200 and r.json()["status"] == "accepted"

    # Accepting connects the two, so the next path is direct.
    path = (await client.get(f"/api/intros/path/{target[0]}", headers=sender[1])).json()
    assert path["kind"] == "direct" and path["strengths"] == [0.5]

    r = await client.post(f"/api/intros/{intro['id']}/rate", headers=sender[1], json={"rating": 5})
    assert r.status_code == 200 and r.json()["status"] == "completed"
    assert r.json()["outcome_rating"] == 5
    again = await client.post(
        f"/api/intros/{intro['id']}/rate", headers=sender[1], json={"rating": 1}
    )
    assert again.status_code == 409

    events = await events_for(session, intro["id"])
    assert [e.type for e in events] == [
        "intro.requested", "intro.forwarded", "intro.accepted", "intro.rated"
    ]  # fmt: skip
    assert [e.actor_id for e in events] == [sender[0], mutual[0], target[0], sender[0]]
    assert all("pre-seed" not in str(e.payload) for e in events)  # no free text in events
    assert events[0].payload == {"is_bridge": True, "via": True, "path": "mutual"}


async def test_mutual_can_decline_and_the_target_never_sees_it(client, trio, session):
    sender, mutual, target = trio
    intro = (await ask(client, sender, target)).json()
    r = await client.post(f"/api/intros/{intro['id']}/decline", headers=mutual[1])
    assert r.status_code == 200 and r.json()["status"] == "declined"
    assert (await inbox(client, target))["received"] == []
    assert (await inbox(client, target))["capacity"]["used"] == 0  # it never reached them
    assert (await inbox(client, mutual))["capacity"]["used"] == 1
    (event,) = [e for e in await events_for(session, intro["id"]) if e.type == "intro.declined"]
    assert event.payload["by"] == "mutual"


async def test_direct_request_when_already_connected(client, trio, session):
    sender, _, target = trio
    await connect(session, sender[0], target[0], 0.6, "worked_together")
    path = (await client.get(f"/api/intros/path/{target[0]}", headers=sender[1])).json()
    assert path["kind"] == "direct" and path["via"] is None
    intro = (await ask(client, sender, target)).json()
    assert intro["via"] is None
    assert (await inbox(client, target))["received"][0]["actions"] == ["accept", "decline"]
    r = await client.post(f"/api/intros/{intro['id']}/decline", headers=target[1])
    assert r.status_code == 200 and r.json()["status"] == "declined"


async def test_no_connection_goes_straight_to_the_target(client, make_member):
    sender = await make_member(role="founder", level=3)
    target = await make_member(role="investor", level=3)
    path = (await client.get(f"/api/intros/path/{target[0]}", headers=sender[1])).json()
    assert path["kind"] == "none" and path["via"] is None and path["can_request"]
    intro = (await ask(client, sender, target)).json()
    assert intro["via"] is None and intro["is_bridge"] is False


async def test_sender_can_pick_another_mutual_and_withdraw(client, trio, make_member, session):
    sender, _, target = trio
    other = await make_member(role="mentor", level=3)
    await connect(session, sender[0], other[0], 0.5)
    await connect(session, other[0], target[0], 0.5)
    path = (await client.get(f"/api/intros/path/{target[0]}", headers=sender[1])).json()
    assert [a["id"] for a in path["alternatives"]] == [str(other[0])]

    stranger = await make_member(role="mentor", level=3)
    r = await ask(client, sender, target, via_member_id=str(stranger[0]))
    assert r.status_code == 422

    intro = (await ask(client, sender, target, via_member_id=str(other[0]))).json()
    assert intro["via"]["id"] == str(other[0])
    r = await client.post(f"/api/intros/{intro['id']}/withdraw", headers=sender[1])
    assert r.status_code == 200 and r.json()["status"] == "withdrawn"
    assert r.json()["actions"] == []


# --- refusals -----------------------------------------------------------------------------


async def test_level_below_3_cannot_request(client, trio, make_member):
    _, _, target = trio
    level2 = await make_member(role="founder", level=2)
    path = (await client.get(f"/api/intros/path/{target[0]}", headers=level2[1])).json()
    assert not path["can_request"] and "level 3" in path["blocked_reason"]
    assert (await ask(client, level2, target)).status_code == 403
    level1 = await make_member(role="founder", level=1)
    r = await client.get(f"/api/intros/path/{target[0]}", headers=level1[1])
    assert r.status_code == 403  # paths come with matches, which need level 2


async def test_one_open_request_per_person_and_not_to_yourself(client, trio):
    sender, _, target = trio
    assert (await ask(client, sender, target)).status_code == 201
    again = await ask(client, sender, target)
    assert again.status_code == 409 and "already have an open request" in again.json()["detail"]
    path = (await client.get(f"/api/intros/path/{target[0]}", headers=sender[1])).json()
    assert path["open_request_id"] and not path["can_request"]
    assert (await ask(client, sender, sender)).status_code == 422


async def test_target_over_capacity_is_refused_politely(client, trio, make_member, session):
    _, mutual, target = trio  # target has 2 slots this week
    senders = [await make_member(role="founder", level=3) for _ in range(3)]
    for s in senders:
        await connect(session, s[0], mutual[0])
    assert (await ask(client, senders[0], target)).status_code == 201
    assert (await ask(client, senders[1], target)).status_code == 201
    r = await ask(client, senders[2], target)
    assert r.status_code == 429
    assert "has had a busy week" in r.json()["detail"] and "please try then" in r.json()["detail"]
    assert 0 < int(r.headers["Retry-After"]) <= 7 * 24 * 3600
    refused = await session.scalar(
        select(Event).where(Event.type == "intro.refused", Event.actor_id == senders[2][0])
    )
    assert refused.payload == {"why": "capacity"}


async def test_a_full_mutual_is_skipped_for_one_with_room(client, trio, make_member, session):
    sender, mutual, target = trio
    await session.execute(
        text("UPDATE members SET open_intro_slots = 0 WHERE id = :id"), {"id": mutual[0]}
    )
    await session.commit()
    r = await ask(client, sender, target)
    assert r.status_code == 429 and "isn't taking intro requests" in r.json()["detail"]

    other = await make_member(role="mentor", level=3, open_intro_slots=2)
    await connect(session, sender[0], other[0], 0.3)
    await connect(session, other[0], target[0], 0.3)
    r = await ask(client, sender, target)
    assert r.status_code == 201 and r.json()["via"]["id"] == str(other[0])


async def test_weekly_sending_limit(trio, make_member, session):
    sender, mutual, _ = trio
    app = create_app(make_test_settings(intro_requests_per_week=1))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        targets = [await make_member(role="investor", level=3) for _ in range(2)]
        assert (await ask(c, sender, targets[0])).status_code == 201
        r = await ask(c, sender, targets[1])
        assert r.status_code == 429 and "weekly limit" in r.json()["detail"]
        assert (await c.get("/api/intros/me", headers=sender[1])).json()["sent_this_week"] == 1
    await get_engine().dispose()


async def test_only_the_right_person_can_act(client, trio, make_member):
    sender, mutual, target = trio
    stranger = await make_member(role="mentor", level=3)
    intro = (await ask(client, sender, target)).json()
    url = f"/api/intros/{intro['id']}"
    assert (await client.post(f"{url}/forward", headers=stranger[1])).status_code == 404
    assert (await client.post(f"{url}/forward", headers=sender[1])).status_code == 403
    assert (await client.post(f"{url}/accept", headers=mutual[1])).status_code == 403
    assert (await client.post(f"{url}/withdraw", headers=mutual[1])).status_code == 403
    r = await client.post(f"{url}/rate", headers=sender[1], json={"rating": 4})
    assert r.status_code == 409  # not accepted yet
    await client.post(f"{url}/forward", headers=mutual[1])
    assert (await client.post(f"{url}/accept", headers=sender[1])).status_code == 403
    assert (await client.post(f"{url}/forward", headers=mutual[1])).status_code == 409
    r = await client.post(f"{url}/rate", headers=target[1], json={"rating": 4})
    assert r.status_code == 403
    unknown = await client.post(f"/api/intros/{uuid.uuid4()}/accept", headers=target[1])
    assert unknown.status_code == 404


async def test_unanswered_requests_expire(client, trio, db_url):
    sender, mutual, target = trio
    stale = (await ask(client, sender, target)).json()
    engine = make_engine(db_url)
    async with AsyncSession(engine) as s:
        await s.execute(
            text("UPDATE intro_requests SET created_at = now() - interval '15 days' WHERE id = :i"),
            {"i": stale["id"]},
        )
        await s.commit()
        assert await expire_stale(s, expiry_days=14) >= 1
        await s.commit()
        assert await s.scalar(
            select(Event.type).where(Event.target_id == stale["id"], Event.type == "intro.expired")
        )
    await engine.dispose()
    assert (await inbox(client, sender))["sent"][0]["status"] == "expired"
    r = await client.post(f"/api/intros/{stale['id']}/forward", headers=mutual[1])
    assert r.status_code == 409
