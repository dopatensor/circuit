"""Exchange circuits (F6) through the API: rounds, loop cards, consent, rating, expiry."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select, text

from app.circuits.service import expire_stale, run_round
from app.models import Circuit, Event
from app.seed.ids import member_id
from tests.conftest import make_test_settings

pytestmark = pytest.mark.anyio
STORY = {member_id(k) for k in ("asha", "priya", "arjun")}
ASHA_CARD = (
    "You help Arjun Nair with hiring, Arjun Nair helps Priya Sharma with fundraising, "
    "Priya Sharma helps you with marketing."
)


@pytest.fixture
async def no_circuits(seeded, session):
    """Start and end with no circuits, so demo-check's story 2 stays reproducible."""
    await session.execute(text("DELETE FROM circuits"))
    await session.commit()
    yield
    await session.execute(text("DELETE FROM circuits"))
    await session.commit()


async def run(client, login, dry_run=False) -> dict:
    r = await client.post(
        "/api/admin/circuits/run", headers=await login("nandini"), params={"dry_run": dry_run}
    )
    assert r.status_code == 200, r.text
    return r.json()


async def story_card(client, login, persona="asha") -> dict:
    cards = (await client.get("/api/circuits/me", headers=await login(persona))).json()
    return next(c for c in cards if {leg["giver"]["id"] for leg in c["legs"]} == {
        str(m) for m in STORY
    })  # fmt: skip


async def test_dry_run_finds_the_story_loop_and_saves_nothing(client, login, session, no_circuits):
    result = await run(client, login, dry_run=True)
    assert result["dry_run"] and result["cycles_found"] >= 1
    story = [c for c in result["circuits"] if {m["id"] for m in c["members"]} == {
        str(m) for m in STORY
    }]  # fmt: skip
    assert len(story) == 1 and story[0]["id"] is None
    assert "Asha Reddy helps Arjun Nair with hiring" in story[0]["sentence"]
    assert await session.scalar(select(func.count()).select_from(Circuit)) == 0


async def test_round_proposes_then_all_accept_then_all_rate(client, login, session, no_circuits):
    result = await run(client, login)
    assert any(c["id"] for c in result["circuits"])

    card = await story_card(client, login)
    assert card["status"] == "proposed" and card["sentence"] == ASHA_CARD
    assert card["actions"] == ["accept", "decline"] and card["my_consent"] == "pending"
    assert card["legs"][0]["giver"]["display_name"] == "Asha Reddy"  # your leg first
    expires = datetime.fromisoformat(card["expires_at"])
    assert timedelta(hours=71) < expires - datetime.now(UTC) <= timedelta(hours=72)

    # Running the round again doesn't put them in a second circuit.
    again = await run(client, login)
    assert not any({m["id"] for m in c["members"]} & {str(m) for m in STORY}
                   for c in again["circuits"])  # fmt: skip

    for persona in ("asha", "priya"):
        r = await client.post(f"/api/circuits/{card['id']}/accept", headers=await login(persona))
        assert r.status_code == 200 and r.json()["status"] == "proposed"
    r = await client.post(f"/api/circuits/{card['id']}/accept", headers=await login("asha"))
    assert r.status_code == 409  # already answered
    r = await client.post(
        f"/api/circuits/{card['id']}/rate", headers=await login("asha"), json={"rating": 5}
    )
    assert r.status_code == 409  # not active yet
    r = await client.post(f"/api/circuits/{card['id']}/accept", headers=await login("arjun"))
    assert r.json()["status"] == "active" and r.json()["actions"] == ["rate"]

    for persona, rating in (("asha", 5), ("priya", 4), ("arjun", 5)):
        r = await client.post(
            f"/api/circuits/{card['id']}/rate",
            headers=await login(persona),
            json={"rating": rating},
        )
        assert r.status_code == 200, r.text
    assert r.json()["status"] == "completed"
    asha_receives = next(
        leg for leg in (await story_card(client, login))["legs"]
        if leg["receiver"]["display_name"] == "Asha Reddy"
    )  # fmt: skip
    assert asha_receives["fulfilled"] and asha_receives["rating"] == 5

    types = (
        await session.scalars(
            select(Event.type).where(Event.target_id == card["id"]).order_by(Event.id)
        )
    ).all()
    assert types == ["circuit.proposed"] + ["circuit.accepted"] * 3 + ["circuit.activated"] + [
        "circuit.leg_rated"
    ] * 3 + ["circuit.completed"]


async def test_one_decline_calls_it_off_and_it_isnt_proposed_again(
    client, login, session, no_circuits
):
    await run(client, login)
    card = await story_card(client, login)
    await client.post(f"/api/circuits/{card['id']}/accept", headers=await login("asha"))
    r = await client.post(f"/api/circuits/{card['id']}/decline", headers=await login("priya"))
    assert r.status_code == 200 and r.json()["status"] == "declined"
    assert (await story_card(client, login, "arjun"))["actions"] == []
    r = await client.post(f"/api/circuits/{card['id']}/accept", headers=await login("arjun"))
    assert r.status_code == 409
    again = await run(client, login, dry_run=True)
    assert not any({m["id"] for m in c["members"]} == {str(m) for m in STORY}
                   for c in again["circuits"])  # fmt: skip


async def test_unanswered_circuits_expire_after_72_hours(client, login, session, no_circuits):
    await run(client, login)
    card = await story_card(client, login)
    later = datetime.now(UTC) + timedelta(hours=73)
    assert await expire_stale(session, later) >= 1
    await session.commit()
    assert (await story_card(client, login))["status"] == "expired"

    # Acting on one whose time ran out (before the hourly job got to it) also expires it.
    await session.execute(text("DELETE FROM circuits"))
    await session.commit()
    await run(client, login)
    card = await story_card(client, login)
    await session.execute(
        text("UPDATE circuits SET expires_at = now() - interval '1 minute' WHERE id = :id"),
        {"id": card["id"]},
    )
    await session.commit()
    r = await client.post(f"/api/circuits/{card['id']}/accept", headers=await login("asha"))
    assert r.status_code == 409 and "expired" in r.json()["detail"]


async def test_only_members_of_the_loop_and_admins(client, login, make_member, no_circuits):
    founder = await login("meera")
    r = await client.post("/api/admin/circuits/run", headers=founder)
    assert r.status_code == 403
    await run(client, login)
    card = await story_card(client, login)
    _, stranger = await make_member(role="founder", level=3)
    r = await client.post(f"/api/circuits/{card['id']}/accept", headers=stranger)
    assert r.status_code == 404
    assert (await client.get("/api/circuits/me", headers=stranger)).json() == []


async def test_scheduled_round_function(session, no_circuits):
    """The weekly job calls run_round; opting out removes you from the next round."""
    await session.execute(
        text("UPDATE members SET circuits_opt_in = false WHERE id = :id"),
        {"id": member_id("priya")},
    )
    await session.commit()
    try:
        result = await run_round(session, make_test_settings(), dry_run=True)
        assert not any(set(c.members) == STORY for c in result.chosen)
    finally:
        await session.rollback()
        await session.execute(
            text("UPDATE members SET circuits_opt_in = true WHERE id = :id"),
            {"id": member_id("priya")},
        )
        await session.commit()
