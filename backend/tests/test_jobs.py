"""Jobs and applications (F11): browsing, matching, applying, founder review."""

import pytest
from sqlalchemy import delete, select, text

from app.models import Event, Job

pytestmark = pytest.mark.anyio

STRONG_BACKEND = {
    "skills": [
        {"capability_id": "backend_development", "level": 3},
        {"capability_id": "data_engineering", "level": 3},
    ]
}


async def student(make_member, client, level=1, skills=STRONG_BACKEND):
    member_id, headers = await make_member(role="student", level=level)
    if skills:
        await client.put("/api/members/me/skills", headers=headers, json=skills)
    return member_id, headers


async def ledgerloop_internship(client, headers) -> dict:
    r = await client.get("/api/jobs", headers=headers, params={"q": "Backend Engineering Intern"})
    return next(j for j in r.json()["items"] if j["startup"]["name"] == "LedgerLoop")


@pytest.fixture
async def terragrid_unclaimed(session):
    reset = text(
        "UPDATE startups SET claimed_by_member_id = NULL WHERE website_domain = 'terragrid.example'"
    )
    await session.execute(reset)
    await session.commit()
    yield
    await session.execute(reset)
    await session.commit()


# --- browsing ---------------------------------------------------------------------------


async def test_ravis_top_job_is_the_story3_internship(client, login):
    r = await client.get("/api/jobs", headers=await login("ravi"), params={"radius_km": 10})
    assert r.status_code == 200, r.text
    top = r.json()["items"][0]
    assert top["title"] == "Backend Engineering Intern"
    assert top["startup"]["name"] == "LedgerLoop"
    assert top["match"]["score"] == 100 and top["paid"] and top["type"] == "internship"
    assert top["distance_km"] < 2


async def test_filters(client, login):
    headers = await login("ravi")
    unpaid = (
        await client.get(
            "/api/jobs", headers=headers, params={"type": "internship", "paid": False, "limit": 100}
        )
    ).json()
    assert unpaid["total"] > 0
    assert all(j["type"] == "internship" and not j["paid"] for j in unpaid["items"])
    ml = (
        await client.get(
            "/api/jobs", headers=headers, params={"capability": "machine_learning", "limit": 100}
        )
    ).json()
    assert ml["total"] > 0
    assert all(
        "machine_learning" in {c["capability_id"] for c in j["capabilities"]} for j in ml["items"]
    )
    near = (
        await client.get("/api/jobs", headers=headers, params={"radius_km": 3, "limit": 100})
    ).json()
    assert all(j["distance_km"] <= 3 for j in near["items"])
    everything = (await client.get("/api/jobs", headers=headers, params={"limit": 1})).json()
    assert everything["total"] > near["total"]
    titled = (
        await client.get("/api/jobs", headers=headers, params={"q": "intern", "limit": 100})
    ).json()
    assert all("intern" in j["title"].lower() for j in titled["items"])


async def test_job_detail_has_match_and_logs_a_view(client, login, session):
    headers = await login("ravi")
    job = await ledgerloop_internship(client, headers)
    r = await client.get(f"/api/jobs/{job['id']}", headers=headers)
    detail = r.json()
    assert detail["match"]["score"] == 100 and detail["has_applied"] is False
    assert {c["capability_id"] for c in detail["capabilities"]} == {
        "backend_development",
        "data_engineering",
    }
    assert "skills, not college names" in detail["description"]
    viewed = await session.scalar(
        select(Event.id).where(Event.type == "job.viewed", Event.target_id == job["id"])
    )
    assert viewed is not None


async def test_non_students_see_no_match(client, login):
    r = await client.get("/api/jobs", headers=await login("meera"), params={"limit": 5})
    assert all(j["match"] is None for j in r.json()["items"])


# --- applying -----------------------------------------------------------------------------


async def test_apply_once_then_track_status(client, login, make_member, session):
    member_id, headers = await student(make_member, client)
    job = await ledgerloop_internship(client, headers)
    r = await client.post(
        f"/api/jobs/{job['id']}/apply", headers=headers, json={"note": "I built a GST parser."}
    )
    assert r.status_code == 201, r.text
    application = r.json()
    assert application["status"] == "submitted" and application["match_score_at_apply"] == 100
    assert application["job"]["startup_claimed"] is True

    again = await client.post(
        f"/api/jobs/{job['id']}/apply", headers=headers, json={"note": "again"}
    )
    assert again.status_code == 409

    mine = (await client.get("/api/applications/me", headers=headers)).json()
    assert [a["id"] for a in mine] == [application["id"]]
    assert (await client.get(f"/api/jobs/{job['id']}", headers=headers)).json()["has_applied"]

    # Deepak (LedgerLoop's founder) sees the applicant, shortlists them.
    deepak = await login("deepak")
    applicants = (
        await client.get(f"/api/startups/{job['startup']['id']}/applicants", headers=deepak)
    ).json()
    mine_listed = next(a for a in applicants if a["application_id"] == application["id"])
    assert "college" not in mine_listed["member"]
    assert mine_listed["note"] == "I built a GST parser."
    r = await client.patch(
        f"/api/applications/{application['id']}", headers=deepak, json={"status": "shortlisted"}
    )
    assert r.status_code == 200 and r.json()["status"] == "shortlisted"
    mine = (await client.get("/api/applications/me", headers=headers)).json()
    assert mine[0]["status"] == "shortlisted" and mine[0]["status_changed_at"]

    types = (
        await session.scalars(
            select(Event.type)
            .where(Event.target_id.in_([job["id"], application["id"]]))
            .order_by(Event.id)
        )
    ).all()
    assert "job.applied" in types and "application.status_changed" in types
    events = (
        await session.scalars(
            select(Event).where(Event.type == "job.applied", Event.actor_id == member_id)
        )
    ).all()
    assert all("GST" not in str(e.payload) for e in events)  # notes are never in events


async def test_applicants_are_ranked_by_skill_match(client, login, make_member):
    _, weak = await student(
        make_member,
        client,
        skills={"skills": [{"capability_id": "backend_development", "level": 1}]},
    )
    _, strong = await student(make_member, client)
    job = await ledgerloop_internship(client, strong)
    await client.post(f"/api/jobs/{job['id']}/apply", headers=weak, json={})
    await client.post(f"/api/jobs/{job['id']}/apply", headers=strong, json={})
    applicants = (
        await client.get(
            f"/api/startups/{job['startup']['id']}/applicants",
            headers=await login("deepak"),
            params={"job_id": job["id"]},
        )
    ).json()
    scores = [a["match"]["score"] for a in applicants]
    assert scores == sorted(scores, reverse=True) and scores[0] == 100


async def test_founder_of_another_startup_cannot_change_status(client, login, make_member):
    _, headers = await student(make_member, client)
    job = await ledgerloop_internship(client, headers)
    application = (
        await client.post(f"/api/jobs/{job['id']}/apply", headers=headers, json={})
    ).json()
    meera = await login("meera")  # founder of HelixRoot, not LedgerLoop
    r = await client.patch(
        f"/api/applications/{application['id']}", headers=meera, json={"status": "rejected"}
    )
    assert r.status_code == 403
    r = await client.get(f"/api/startups/{job['startup']['id']}/applicants", headers=meera)
    assert r.status_code == 403


async def test_student_without_the_right_level_cannot_apply(client, login, make_member):
    _, headers = await student(make_member, client, level=0)
    job = await ledgerloop_internship(client, await login("ravi"))
    r = await client.post(f"/api/jobs/{job['id']}/apply", headers=headers, json={})
    assert r.status_code == 403
    assert "level 1" in r.json()["detail"]


async def test_only_students_apply(client, login):
    headers = await login("kavya")
    job = await ledgerloop_internship(client, headers)
    assert (
        await client.post(f"/api/jobs/{job['id']}/apply", headers=headers, json={})
    ).status_code == 403


async def test_note_is_short(client, login, make_member):
    _, headers = await student(make_member, client)
    job = await ledgerloop_internship(client, headers)
    r = await client.post(f"/api/jobs/{job['id']}/apply", headers=headers, json={"note": "x" * 501})
    assert r.status_code == 422


async def test_withdrawn_application_cannot_be_changed_by_founder(client, login, make_member):
    _, headers = await student(make_member, client)
    job = await ledgerloop_internship(client, headers)
    application = (
        await client.post(f"/api/jobs/{job['id']}/apply", headers=headers, json={})
    ).json()
    r = await client.post(f"/api/applications/{application['id']}/withdraw", headers=headers)
    assert r.json()["status"] == "withdrawn"
    r = await client.patch(
        f"/api/applications/{application['id']}",
        headers=await login("deepak"),
        json={"status": "hired"},
    )
    assert r.status_code == 409


async def test_unknown_job_is_404(client, login):
    r = await client.post(
        "/api/jobs/00000000-0000-0000-0000-000000000000/apply", headers=await login("ravi"), json={}
    )
    assert r.status_code == 404


# --- unclaimed startups: applications wait for the founder ----------------------------------


async def test_application_to_unclaimed_startup_appears_when_founder_claims(
    client, login, make_member, terragrid_unclaimed
):
    _, headers = await student(
        make_member, client, skills={"skills": [{"capability_id": "data_analysis", "level": 3}]}
    )
    jobs = (
        await client.get("/api/jobs", headers=headers, params={"q": "Energy Data Analyst"})
    ).json()
    job = next(j for j in jobs["items"] if j["startup"]["name"] == "TerraGrid Energy")
    assert job["startup"]["claimed"] is False
    application = (
        await client.post(f"/api/jobs/{job['id']}/apply", headers=headers, json={"note": "Hi"})
    ).json()
    assert application["job"]["startup_claimed"] is False

    sid = job["startup"]["id"]
    rohan = await login("rohan")
    stats = (await client.get(f"/api/startups/{sid}/stats", headers=rohan)).json()
    assert stats["applications_waiting"] >= 1
    assert (await client.get(f"/api/startups/{sid}/applicants", headers=rohan)).status_code == 403

    claim = (
        await client.post(
            f"/api/startups/{sid}/claim", headers=rohan, json={"email": "rohan@terragrid.example"}
        )
    ).json()
    await client.post(
        f"/api/startups/{sid}/claim/verify", headers=rohan,
        json={"claim_id": claim["claim_id"], "code": claim["dev_code"]},
    )  # fmt: skip
    applicants = (await client.get(f"/api/startups/{sid}/applicants", headers=rohan)).json()
    assert application["id"] in {a["application_id"] for a in applicants}


# --- founders manage jobs -------------------------------------------------------------------


async def test_founder_posts_edits_and_closes_a_job(client, login, session):
    deepak = await login("deepak")
    ledger = (await client.get("/api/startups", headers=deepak, params={"q": "LedgerLoop"})).json()[
        "items"
    ][0]
    body = {
        "title": "Data Engineering Intern",
        "type": "internship",
        "paid": False,
        "compensation": "Unpaid (certificate)",
        "capabilities": [{"capability_id": "data_engineering", "min_level": 1}],
    }
    r = await client.post(f"/api/startups/{ledger['id']}/jobs", headers=deepak, json=body)
    assert r.status_code == 201, r.text
    job = r.json()
    try:
        assert job["capabilities"] == [{"capability_id": "data_engineering", "min_level": 1}]
        assert (
            await client.post(
                f"/api/startups/{ledger['id']}/jobs", headers=await login("meera"), json=body
            )
        ).status_code == 403
        r = await client.patch(
            f"/api/jobs/{job['id']}",
            headers=deepak,
            json={"paid": True, "compensation": "₹10,000/month"},
        )
        assert r.json()["paid"] is True
        r = await client.patch(f"/api/jobs/{job['id']}", headers=deepak, json={"status": "closed"})
        assert r.json()["status"] == "closed"
        listed = (
            await client.get("/api/jobs", headers=deepak, params={"q": "Data Engineering Intern"})
        ).json()
        assert job["id"] not in {j["id"] for j in listed["items"]}  # closed jobs are hidden
        r = await client.post(f"/api/jobs/{job['id']}/apply", headers=await login("ravi"), json={})
        assert r.status_code == 409
    finally:
        await session.execute(delete(Job).where(Job.id == job["id"]))
        await session.commit()


async def test_map_pins_show_jobs(client, login):
    r = await client.get(
        "/api/map/startups/nearby", headers=await login("ravi"), params={"radius_km": 3}
    )
    ledger = next(p for p in r.json()["items"] if p["name"] == "LedgerLoop")
    assert {j["title"] for j in ledger["jobs"]} == {
        "Backend Engineering Intern",
        "Junior Backend Engineer",
    }
    assert ledger["match"]["score"] == 100
