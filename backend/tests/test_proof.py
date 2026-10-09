"""Proof of work beyond GitHub (portfolio, Behance, Dribbble, case studies), privacy,
and how proof feeds matching and applicant ranking."""

import uuid

import pytest
from sqlalchemy import select

from app.models import GitHubAccount, GitHubRepo, MatchResult
from app.seed.ids import member_id
from app.seed.stories import STORY3_JOB_TITLE
from tests.test_jobs import ledgerloop_internship, student

pytestmark = pytest.mark.anyio

CASE_STUDY = (
    "Ran 12 interviews with kirana owners, mapped how they bill, and designed a checkout "
    "flow that cut the number of taps from nine to four. Tested it in three shops over two "
    "weeks and the owners kept using it after the test ended."
)


async def test_add_portfolio_links_and_case_studies(client, make_member):
    member_id_, headers = await make_member(role="student", level=1)
    r = await client.post(
        "/api/proof/items",
        headers=headers,
        json={
            "url": "https://www.behance.net/someone/project",
            "title": "Checkout redesign",
            "description": "Five rounds of tests with shop owners.",
            "capability_ids": ["ui_ux_design"],
        },
    )
    assert r.status_code == 201 and r.json()["kind"] == "behance"
    r = await client.post(
        "/api/proof/items",
        headers=headers,
        json={"url": "https://dribbble.com/shots/1", "title": "Icons", "capability_ids": []},
    )
    assert r.json()["kind"] == "dribbble"
    r = await client.post(
        "/api/proof/items",
        headers=headers,
        json={"url": "https://my.portfolio.example", "title": "Site", "kind": "website"},
    )
    assert r.json()["kind"] == "website"
    r = await client.post(
        "/api/proof/items",
        headers=headers,
        json={"title": "Brand kit", "description": CASE_STUDY, "capability_ids": ["brand_design"]},
    )
    assert r.json()["kind"] == "case_study" and r.json()["url"] is None

    me = (await client.get("/api/proof/me", headers=headers)).json()
    assert [i["kind"] for i in me["items"]] == ["behance", "dribbble", "website", "case_study"]
    public = (await client.get(f"/api/members/{member_id_}", headers=headers)).json()
    assert len(public["proof"]["items"]) == 4


async def test_case_study_without_a_link_needs_a_write_up(client, make_member):
    _, headers = await make_member(role="student", level=1)
    r = await client.post("/api/proof/items", headers=headers, json={"title": "Stuff"})
    assert r.status_code == 422
    assert "40 characters" in r.json()["detail"]


async def test_only_your_own_items_can_change(client, make_member):
    _, alice = await make_member(role="student", level=1)
    _, bob = await make_member(role="student", level=1)
    item = (
        await client.post(
            "/api/proof/items", headers=alice,
            json={"url": "https://a.example", "title": "A"},
        )
    ).json()  # fmt: skip
    assert (
        await client.patch(f"/api/proof/items/{item['id']}", headers=bob, json={"title": "B"})
    ).status_code == 404
    assert (await client.delete(f"/api/proof/items/{item['id']}", headers=bob)).status_code == 404
    r = await client.patch(
        f"/api/proof/items/{item['id']}",
        headers=alice,
        json={"title": "Better", "capability_ids": ["frontend_development"]},
    )
    assert r.json()["title"] == "Better" and r.json()["capability_ids"] == ["frontend_development"]
    assert (await client.delete(f"/api/proof/items/{item['id']}", headers=alice)).status_code == 204
    assert (await client.get("/api/proof/me", headers=alice)).json()["items"] == []


async def test_proof_is_for_students(client, login):
    r = await client.post(
        "/api/proof/items", headers=await login("meera"),
        json={"url": "https://a.example", "title": "A"},
    )  # fmt: skip
    assert r.status_code == 403


async def test_students_can_hide_their_college(client, make_member):
    member_id_, headers = await make_member(
        role="student", level=1, college="Shantinagar Institute of Technology"
    )
    public = (await client.get(f"/api/members/{member_id_}", headers=headers)).json()
    assert public["college"] == "Shantinagar Institute of Technology"
    me = await client.patch("/api/members/me", headers=headers, json={"show_college": False})
    assert me.json()["show_college"] is False
    assert me.json()["college"] == "Shantinagar Institute of Technology"  # you still see it
    public = (await client.get(f"/api/members/{member_id_}", headers=headers)).json()
    assert public["college"] is None


# --- proof in scoring -----------------------------------------------------------------------


async def give_github(session, member: uuid.UUID, caps_languages: dict[str, int]):
    account = GitHubAccount(
        member_id=member, github_user_id=int(uuid.uuid4().int % 10**12), login="t",
        profile_url="https://github.example/t", source="seed", status="ok",
        active_weeks_90d=4, external_prs_total=2,
    )  # fmt: skip
    session.add(account)
    await session.flush()
    for i in range(3):
        session.add(
            GitHubRepo(
                member_id=member, github_repo_id=i, name=f"r{i}", html_url="https://x.example",
                languages=caps_languages, frameworks=["Airflow"], commits_by_user=20,
            )
        )  # fmt: skip
    await session.commit()


async def test_applicants_with_proof_rank_above_equal_skills(client, login, make_member, session):
    plain_id, plain = await student(make_member, client)
    proven_id, proven = await student(make_member, client)
    await give_github(session, proven_id, {"Python": 1000})
    job = await ledgerloop_internship(client, plain)
    await client.post(f"/api/jobs/{job['id']}/apply", headers=plain, json={})
    await client.post(f"/api/jobs/{job['id']}/apply", headers=proven, json={})
    applicants = (
        await client.get(
            f"/api/startups/{job['startup']['id']}/applicants",
            headers=await login("deepak"),
            params={"job_id": job["id"]},
        )
    ).json()
    ours = [a for a in applicants if a["member"]["id"] in (str(plain_id), str(proven_id))]
    assert [a["member"]["id"] for a in ours] == [str(proven_id), str(plain_id)]
    first, second = ours
    assert first["match"]["score"] == second["match"]["score"]  # same skills
    assert first["rank_score"] > second["rank_score"]
    assert set(first["proof"]["verified_capabilities"]) == {
        "backend_development",
        "data_engineering",
    }
    assert first["proof"]["components"]["github_signal"] == pytest.approx(0.03)
    assert second["proof"]["components"]["github_signal"] == 0
    assert "college" not in str(first)


async def test_ravis_top_match_is_still_the_story3_internship(client, login, session, seeded):
    headers = await login("ravi")
    matches = (await client.get("/api/matches", headers=headers)).json()
    top = matches["items"][0] if isinstance(matches, dict) else matches[0]
    assert STORY3_JOB_TITLE in str(top)
    row = await session.scalar(
        select(MatchResult)
        .where(MatchResult.member_id == member_id("ravi"))
        .order_by(MatchResult.score.desc())
        .limit(1)
    )
    assert row.components["github_signal"] == pytest.approx(0.03)  # verified by GitHub
    assert row.components["skill_match"] == 100
