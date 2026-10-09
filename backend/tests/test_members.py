"""Profiles, traits, skills, needs and offers."""

import pytest
from sqlalchemy import select

from app.models import Event

pytestmark = pytest.mark.anyio


async def test_own_profile_has_private_fields(client, login):
    me = (await client.get("/api/members/me", headers=await login("ravi"))).json()
    assert me["display_name"] == "Ravi Kumar"
    assert me["college"] == "Shantinagar Institute of Technology"
    assert {"capability_id": "backend_development", "level": 3} in me["skills"]
    assert me["location"]["lat"] and me["is_demo"] is True


async def test_public_profile_hides_exact_location(client, login):
    ravi = (await client.get("/api/members/me", headers=await login("ravi"))).json()
    r = await client.get(f"/api/members/{ravi['id']}", headers=await login("meera"))
    assert r.status_code == 200
    public = r.json()
    assert "location" not in public and "skills" not in public and "linkedin_url" not in public
    assert public["city"] == "Bengaluru"


async def test_founder_profile_lists_their_startup(client, login):
    me = (await client.get("/api/members/me", headers=await login("meera"))).json()
    assert me["startups"][0]["name"] == "HelixRoot Biosciences"
    assert me["startups"][0]["is_claimer"] is True
    assert {o["capability_id"] for o in me["offers"]} == {"lab_research"}


async def test_profile_says_when_you_are_on_a_team_but_did_not_claim_it(client, login):
    # Rohan is on TerraGrid's team, but the page is unclaimed (the claim-flow story).
    me = (await client.get("/api/members/me", headers=await login("rohan"))).json()
    terragrid = next(s for s in me["startups"] if s["name"] == "TerraGrid Energy")
    assert terragrid["is_claimer"] is False


async def test_update_profile_and_linkedin_raises_level_to_2(client, make_member):
    _, headers = await make_member(level=1)
    r = await client.patch(
        "/api/members/me",
        headers=headers,
        json={"bio": "Building in climate.", "location": {"lat": 12.97, "lng": 77.59}},
    )
    assert r.status_code == 200
    assert r.json()["bio"] == "Building in climate."
    assert r.json()["location"] == {"lat": 12.97, "lng": 77.59}

    bad = await client.patch(
        "/api/members/me", headers=headers, json={"linkedin_url": "https://evil.example/in/x"}
    )
    assert bad.status_code == 422
    r = await client.patch(
        "/api/members/me", headers=headers, json={"linkedin_url": "https://www.linkedin.com/in/x"}
    )
    assert r.json()["verification_level"] == 2


async def test_traits_and_skills(client, make_member):
    _, headers = await make_member(role="student", level=1)
    r = await client.put(
        "/api/members/me/traits",
        headers=headers,
        json={"trait_ids": ["b2b", "b2b", "remote_first"]},
    )
    assert r.json()["trait_ids"] == ["b2b", "remote_first"]
    r = await client.put(
        "/api/members/me/skills",
        headers=headers,
        json={"skills": [{"capability_id": "frontend_development", "level": 3}]},
    )
    assert r.json()["skills"] == [{"capability_id": "frontend_development", "level": 3}]
    bad = await client.put("/api/members/me/traits", headers=headers, json={"trait_ids": ["vibes"]})
    assert bad.status_code == 422


async def test_needs_and_offers_lifecycle(client, make_member, session):
    member_id, headers = await make_member(level=1)
    _, other = await make_member(level=1)

    r = await client.post(
        "/api/members/me/needs",
        headers=headers,
        json={"capability_id": "regulatory_affairs", "text": "CDSCO approval help"},
    )
    assert r.status_code == 201
    need = r.json()
    assert (
        await client.post(
            "/api/members/me/needs", headers=headers, json={"capability_id": "made_up"}
        )
    ).status_code == 422

    r = await client.patch(f"/api/needs/{need['id']}", headers=headers, json={"text": "New text"})
    assert r.json()["text"] == "New text"
    assert (
        await client.patch(f"/api/needs/{need['id']}", headers=other, json={"text": "x"})
    ).status_code == 403
    assert (await client.delete(f"/api/needs/{need['id']}", headers=headers)).status_code == 204
    me = (await client.get("/api/members/me", headers=headers)).json()
    assert me["needs"] == []  # retired needs are hidden

    r = await client.post(
        "/api/members/me/offers", headers=headers, json={"capability_id": "hiring", "text": "x"}
    )
    offer = r.json()
    assert (await client.delete(f"/api/offers/{offer['id']}", headers=other)).status_code == 403
    assert (await client.delete(f"/api/offers/{offer['id']}", headers=headers)).status_code == 204

    # Events record what happened, never the free text people typed.
    events = (
        await session.scalars(select(Event).where(Event.actor_id == member_id).order_by(Event.id))
    ).all()
    types = [e.type for e in events]
    assert types == [
        "need.created",
        "need.updated",
        "need.retired",
        "offer.created",
        "offer.retired",
    ]
    assert all("CDSCO" not in str(e.payload) and "New text" not in str(e.payload) for e in events)


async def test_browse_members(client, login):
    headers = await login("ravi")
    r = await client.get("/api/members", headers=headers, params={"role": "mentor", "limit": 5})
    page = r.json()
    assert page["total"] >= 30 and len(page["items"]) == 5
    assert all(m["role"] == "mentor" for m in page["items"])
    r = await client.get("/api/members", headers=headers, params={"q": "Lakshmi"})
    assert [m["display_name"] for m in r.json()["items"]] == ["Dr. Lakshmi Narayan"]


async def test_unknown_member_is_404(client, login):
    r = await client.get(
        "/api/members/00000000-0000-0000-0000-000000000000", headers=await login("ravi")
    )
    assert r.status_code == 404


async def test_delete_my_profile(client, make_member):
    _, headers = await make_member(level=1)
    await client.post("/api/members/me/needs", headers=headers, json={"capability_id": "hiring"})
    assert (await client.delete("/api/members/me", headers=headers)).status_code == 204
    assert (await client.get("/api/members/me", headers=headers)).status_code == 403
