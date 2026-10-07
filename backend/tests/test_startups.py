"""Startup CRUD: browse, add, edit (claimer only), and startup needs."""

import uuid

import pytest

pytestmark = pytest.mark.anyio


def new_startup(**overrides) -> dict:
    body = {
        "name": "Test Startup",
        "website_domain": f"test-{uuid.uuid4().hex[:8]}.example",
        "description": "Testing.",
        "sector": "saas",
        "location": {"lat": 12.98, "lng": 77.6},
        "hiring": True,
    }
    body.update(overrides)
    return body


async def test_browse_and_filter(client, login):
    headers = await login("ravi")
    r = await client.get("/api/startups", headers=headers, params={"hiring": True, "limit": 100})
    page = r.json()
    assert page["total"] > 50 and all(s["hiring"] for s in page["items"])
    r = await client.get("/api/startups", headers=headers, params={"q": "HelixRoot"})
    (helix,) = r.json()["items"]
    assert helix["claimed"] and helix["sector"] == "biotech"
    assert {"long_sales_cycle", "technical_buyers"} <= set(helix["trait_ids"])
    assert helix["team"][0]["display_name"] == "Dr. Meera Iyer"
    unclaimed = await client.get("/api/startups", headers=headers, params={"claimed": False})
    assert unclaimed.json()["total"] > 50


async def test_founder_adds_edits_and_deletes_a_startup(client, make_member):
    _, founder = await make_member(role="founder", level=1)
    _, someone = await make_member(role="founder", level=1)
    r = await client.post("/api/startups", headers=founder, json=new_startup())
    assert r.status_code == 201, r.text
    s = r.json()
    assert s["source"] == "user" and s["claimed"] and len(s["team"]) == 1

    r = await client.patch(f"/api/startups/{s['id']}", headers=founder, json={"hiring": False})
    assert r.json()["hiring"] is False
    assert (
        await client.patch(f"/api/startups/{s['id']}", headers=someone, json={"hiring": True})
    ).status_code == 403

    r = await client.post(
        f"/api/startups/{s['id']}/needs", headers=founder, json={"capability_id": "fundraising"}
    )
    assert r.status_code == 201 and r.json()["owner_type"] == "startup"
    assert (await client.delete(f"/api/startups/{s['id']}", headers=someone)).status_code == 403
    assert (await client.delete(f"/api/startups/{s['id']}", headers=founder)).status_code == 204


async def test_duplicate_domain_points_to_claim(client, make_member):
    _, founder = await make_member(role="founder", level=1)
    r = await client.post(
        "/api/startups", headers=founder, json=new_startup(website_domain="WWW.TerraGrid.example")
    )
    assert r.status_code == 409
    assert "claim" in r.json()["detail"]["message"]


async def test_only_founders_add_startups(client, make_member):
    _, student = await make_member(role="student", level=1)
    assert (
        await client.post("/api/startups", headers=student, json=new_startup())
    ).status_code == 403


async def test_seeded_startups_cannot_be_deleted(client, login):
    headers = await login("meera")
    helix = (await client.get("/api/startups", headers=headers, params={"q": "HelixRoot"})).json()
    sid = helix["items"][0]["id"]
    assert (await client.delete(f"/api/startups/{sid}", headers=headers)).status_code == 409


async def test_unclaimed_startup_cannot_be_edited(client, login):
    headers = await login("rohan")  # on TerraGrid's team, but hasn't claimed it yet
    terra = (await client.get("/api/startups", headers=headers, params={"q": "TerraGrid"})).json()
    sid = terra["items"][0]["id"]
    assert (
        await client.patch(f"/api/startups/{sid}", headers=headers, json={"hiring": False})
    ).status_code == 403
