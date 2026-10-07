"""Partner dashboard (F8): gaps by capability and area, stats, local vs bridge intros.

The test database holds the demo seed, so most checks measure the change caused by a
few rows the test adds (and removes), which gives exact numbers.
"""

import math

import pytest
from sqlalchemy import select

from app.dashboard import Acceptance, grid_degrees
from app.models import Event, IntroRequest

pytestmark = pytest.mark.anyio
FAR_AWAY = {"lat": 1.0005, "lng": 1.0005}  # nothing in the seed is near here


def test_grid_cells_are_square_in_km():
    dlat, dlng = grid_degrees(1.0, 60.0)
    assert dlat == pytest.approx(1 / 111.32)
    assert dlng == pytest.approx(2 * dlat)  # cos(60°) = 0.5
    assert grid_degrees(2.0, 0.0)[1] == pytest.approx(2 / 111.32)


def test_acceptance_rate():
    assert Acceptance(4, 3).rate == 0.75
    assert Acceptance(0, 0).rate is None


async def get(client, headers, path, **params) -> dict:
    r = await client.get(path, headers=headers, params=params)
    assert r.status_code == 200, r.text
    return r.json()


async def test_story5_regulatory_is_the_biggest_gap(client, login):
    gaps = (await get(client, await login("nandini"), "/api/dashboard/gaps"))["items"]
    top = gaps[0]
    assert (top["capability_id"], top["needs"], top["offers"]) == ("regulatory_affairs", 35, 2)
    assert [g["gap"] for g in gaps] == sorted((g["gap"] for g in gaps), reverse=True)


async def test_only_partner_admins(client, login, make_member):
    for headers in (await login("meera"), (await make_member(role="partner_admin", level=2))[1]):
        for path in ("gaps", "gaps/areas", "stats", "intros"):
            r = await client.get(f"/api/dashboard/{path}", headers=headers)
            assert r.status_code == 403, path


async def test_new_needs_and_offers_move_the_gap_and_the_map(client, login, make_member):
    admin = await login("nandini")
    before = {
        g["capability_id"]: g
        for g in (await get(client, admin, "/api/dashboard/gaps", limit=100))["items"]
    }
    _, needy = await make_member(role="founder", level=1)
    await client.patch("/api/members/me", headers=needy, json={"location": FAR_AWAY})
    for _ in range(2):
        r = await client.post(
            "/api/members/me/needs", headers=needy,
            json={"capability_id": "regulatory_affairs", "text": "Device approval help"},
        )  # fmt: skip
        assert r.status_code == 201, r.text
    _, helper = await make_member(role="mentor", level=1)
    await client.patch("/api/members/me", headers=helper, json={"location": FAR_AWAY})
    await client.post(
        "/api/members/me/offers", headers=helper,
        json={"capability_id": "regulatory_affairs", "text": "Former regulator"},
    )  # fmt: skip

    after = {
        g["capability_id"]: g
        for g in (await get(client, admin, "/api/dashboard/gaps", limit=100))["items"]
    }
    reg_before, reg_after = before["regulatory_affairs"], after["regulatory_affairs"]
    assert (reg_after["needs"], reg_after["offers"]) == (
        reg_before["needs"] + 2, reg_before["offers"] + 1
    )  # fmt: skip

    areas = await get(
        client, admin, "/api/dashboard/gaps/areas", capability="regulatory_affairs", cell_km=1
    )
    assert areas["cell_km"] == 1 and areas["capability_id"] == "regulatory_affairs"
    near = [
        c for c in areas["cells"]
        if math.dist((c["lat"], c["lng"]), (FAR_AWAY["lat"], FAR_AWAY["lng"])) < 0.01
    ]  # fmt: skip
    assert len(near) == 1 and (near[0]["needs"], near[0]["offers"], near[0]["gap"]) == (2, 1, 1)
    # Filtering by another capability leaves this cell out.
    other = await get(client, admin, "/api/dashboard/gaps/areas", capability="hiring", cell_km=1)
    assert not any(abs(c["lat"] - 1.0) < 0.01 for c in other["cells"])
    r = await client.get("/api/dashboard/gaps/areas", headers=admin, params={"capability": "nope"})
    assert r.status_code == 422


async def test_intro_acceptance_local_vs_bridge(client, login, make_member, session):
    admin = await login("nandini")
    before = await get(client, admin, "/api/dashboard/intros")
    a, _ = await make_member(role="founder", level=3)
    b, _ = await make_member(role="mentor", level=3)
    rows = [
        ("accepted", True), ("completed", True), ("declined", True),  # bridge: 2 of 3
        ("expired", False),  # local: 0 of 1
        ("withdrawn", False), ("pending", False), ("forwarded", True),  # not decided
    ]  # fmt: skip
    session.add_all(
        IntroRequest(from_member=a, to_member=b, status=s, is_bridge=bridge, reason="test")
        for s, bridge in rows
    )
    await session.commit()
    after = await get(client, admin, "/api/dashboard/intros")
    for group, decided, accepted in (("bridge", 3, 2), ("local", 1, 0)):
        assert after[group]["decided"] == before[group]["decided"] + decided
        assert after[group]["accepted"] == before[group]["accepted"] + accepted
        assert after[group]["rate"] == round(after[group]["accepted"] / after[group]["decided"], 3)


async def test_seed_shows_bridge_intros_accepted_more_often(client, login):
    result = await get(client, await login("nandini"), "/api/dashboard/intros")
    assert result["bridge"]["rate"] > result["local"]["rate"]


async def test_stats_and_view_events(client, login, session):
    admin = await login("nandini")
    stats = await get(client, admin, "/api/dashboard/stats")
    assert stats["members"] == sum(stats["members_by_role"].values())
    assert stats["members_by_role"]["student"] >= 100
    assert 0 < stats["startups_claimed"] < stats["startups"]
    assert stats["intros_accepted"] <= stats["intros"]
    assert stats["students_interested"] > 0
    sections = (
        await session.scalars(select(Event.payload["section"].astext).where(
            Event.type == "dashboard.viewed"
        ))
    ).all()  # fmt: skip
    assert "stats" in sections
