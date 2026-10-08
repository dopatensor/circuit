"""Matching against the seeded database (fake embeddings): stories, rules and API."""

import pytest
from sqlalchemy import text

from app.graph import PostgresGraph
from app.matching.service import compute_for_member, load_context, network_matches
from app.seed.ids import member_id
from tests.conftest import make_test_settings

pytestmark = pytest.mark.anyio
SETTINGS = make_test_settings()


async def top(client, headers, n=20):
    r = await client.get("/api/matches", headers=headers, params={"limit": n})
    assert r.status_code == 200, r.text
    return r.json()["items"]


# --- the demo stories -------------------------------------------------------------------


async def test_story1_meera_sees_kavya_as_a_bridge_match_with_a_reason(client, login):
    items = await top(client, await login("meera"), 5)
    kavya = next(m for m in items if m["title"] == "Kavya Menon")
    assert kavya["is_bridge"]
    assert "offers marketing, which you need" in kavya["reason"]
    assert "long sales cycle" in kavya["reason"] and "technical buyers" in kavya["reason"]
    assert items[0]["title"] == "Kavya Menon"


async def test_story1_from_kavyas_side(client, login):
    items = await top(client, await login("kavya"), 10)
    assert {"Dr. Meera Iyer", "HelixRoot Biosciences"} & {m["title"] for m in items}


async def test_matches_say_who_an_intro_would_go_to(client, login, session):
    items = await top(client, await login("kavya"), 50)
    people = [m for m in items if m["candidate_type"] == "member"]
    startups = [m for m in items if m["candidate_type"] == "startup"]
    assert people and startups
    # People: the person themselves.
    assert all(m["intro_member_id"] == m["candidate_id"] for m in people)
    # Startups: the founder who claimed it, or nobody yet.
    claimed_by = dict(
        (await session.execute(text("SELECT id::text, claimed_by_member_id::text FROM startups")))
        .tuples()
        .all()
    )
    assert all(m["intro_member_id"] == claimed_by[m["candidate_id"]] for m in startups)
    # Jobs (students) have no intro target.
    ravi = await top(client, await login("ravi"))
    assert all(m["intro_member_id"] is None for m in ravi if m["candidate_type"] == "job")


async def test_story3_ravis_top_match_is_the_internship(client, login):
    items = await top(client, await login("ravi"))
    first = items[0]
    assert first["candidate_type"] == "job"
    assert first["title"] == "Backend Engineering Intern"
    assert first["subtitle"].startswith("LedgerLoop")
    assert first["components"]["skill_match"] == 100
    assert "1.1 km away · paid internship" in first["reason"]


async def test_student_matches_respect_the_distance_limit(client, login):
    items = await top(client, await login("ravi"), 50)
    assert items and all(
        m["components"]["distance_km"] <= SETTINGS.student_radius_km for m in items
    )
    assert all(m["candidate_type"] == "job" for m in items)
    startups = [m["components"]["startup_id"] for m in items]
    assert len(startups) == len(set(startups))  # one job per startup


async def test_story4_rohan_reaches_vikram_through_lakshmi(client, login):
    items = await top(client, await login("rohan"), 5)
    vikram = next(m for m in items if m["title"] == "Vikram Shah")
    assert vikram["components"]["hops"] == 2
    assert "you both know Dr. Lakshmi Narayan" in vikram["reason"]


async def test_story2_circuit_members_match_each_other(client, login):
    asha = {m["title"] for m in await top(client, await login("asha"), 20)}
    assert {"Priya Sharma", "Arjun Nair"} <= asha


# --- rules --------------------------------------------------------------------------------


async def test_about_a_quarter_are_bridge_matches(client, login):
    items = await top(client, await login("lakshmi"), 20)
    assert len(items) == 20
    assert sum(m["is_bridge"] for m in items) >= 5


async def test_never_matched_with_yourself_or_your_own_team(session, seeded):
    ctx = await load_context(session)
    meera = member_id("meera")
    ids = {m.candidate_id for m in network_matches(ctx, meera, SETTINGS)}
    helix = await session.scalar(
        text("SELECT id FROM startups WHERE website_domain = 'helixroot.example'")
    )
    assert meera not in ids and helix not in ids


async def test_people_at_capacity_are_left_out(session, seeded):
    kavya = member_id("kavya")
    await session.execute(
        text("UPDATE members SET open_intro_slots = 0 WHERE id = :k"), {"k": kavya}
    )
    try:
        ctx = await load_context(session)
        ids = {m.candidate_id for m in network_matches(ctx, member_id("meera"), SETTINGS)}
        assert kavya not in ids
    finally:
        await session.rollback()


async def test_candidate_sources_are_recorded(client, login):
    items = await top(client, await login("lakshmi"), 20)
    assert {m["components"]["source"] for m in items} <= {"local", "bridge", "both"}
    assert any(m["components"]["source"] in ("bridge", "both") for m in items)


async def test_partner_admins_get_no_matches(session, seeded):
    assert await compute_for_member(session, member_id("nandini"), SETTINGS) == 0
    await session.rollback()


async def test_graph_paths_use_recursive_sql(session, seeded):
    paths = await PostgresGraph().paths(session, member_id("rohan"), member_id("vikram"))
    assert paths and paths[0].members[1] == member_id("lakshmi") and paths[0].weakest >= 0.8


# --- API ----------------------------------------------------------------------------------


async def test_matches_need_level_2(client, make_member):
    _, headers = await make_member(role="founder", level=1)
    r = await client.get("/api/matches", headers=headers)
    assert r.status_code == 403 and "level 2" in r.json()["detail"]


async def test_new_member_gets_matches_computed_on_demand(client, make_member):
    _, headers = await make_member(role="founder", level=2, sector="saas")
    await client.post(
        "/api/members/me/needs", headers=headers, json={"capability_id": "regulatory_affairs"}
    )
    items = await top(client, headers)
    assert any(m["title"] in ("Dr. Sunil Bhat", "Farah Siddiqui") for m in items)


async def test_refresh_picks_up_a_new_need(client, make_member):
    _, headers = await make_member(role="founder", level=2, sector="saas")
    await client.post(
        "/api/members/me/needs", headers=headers, json={"capability_id": "pitch_coaching"}
    )
    before = await top(client, headers)
    await client.post(
        "/api/members/me/needs", headers=headers, json={"capability_id": "regulatory_affairs"}
    )
    r = await client.post("/api/matches/refresh", headers=headers)
    after = r.json()["items"]
    assert {m["candidate_id"] for m in after} != {m["candidate_id"] for m in before}
    assert any("regulatory affairs" in m["reason"] for m in after)


async def test_admin_recompute(client, login):
    r = await client.post("/api/admin/matches/recompute", headers=await login("nandini"))
    assert r.status_code == 200 and r.json()["results"] > 1000
    assert (
        await client.post("/api/admin/matches/recompute", headers=await login("meera"))
    ).status_code == 403
