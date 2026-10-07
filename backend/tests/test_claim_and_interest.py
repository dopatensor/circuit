"""Views, "I'm interested", stats, and claiming a startup by domain email (F2/F3)."""

import httpx
import pytest
from sqlalchemy import text

from app.main import create_app
from tests.conftest import make_test_settings

pytestmark = pytest.mark.anyio


async def startup_id(client, headers, name: str) -> str:
    r = await client.get("/api/startups", headers=headers, params={"q": name})
    return r.json()["items"][0]["id"]


@pytest.fixture
async def terragrid_unclaimed(session):
    """Make sure TerraGrid is unclaimed before and after the test (it's seeded data)."""
    reset = text(
        "UPDATE startups SET claimed_by_member_id = NULL WHERE website_domain = 'terragrid.example'"
    )
    await session.execute(reset)
    await session.commit()
    yield
    await session.execute(reset)
    await session.commit()


# --- views and interest -------------------------------------------------------------------


async def test_views_count_once_per_person_per_day_and_not_for_the_team(client, login, make_member):
    meera = await login("meera")
    sid = await startup_id(client, meera, "HelixRoot")
    before = (await client.get(f"/api/startups/{sid}/stats", headers=meera)).json()["view_count"]

    _, student = await make_member(role="student", level=1)
    await client.get(f"/api/startups/{sid}", headers=student)
    await client.get(f"/api/startups/{sid}", headers=student)  # same person again: no count
    await client.get(f"/api/startups/{sid}", headers=meera)  # her own startup: no count
    stats = (await client.get(f"/api/startups/{sid}/stats", headers=meera)).json()
    assert stats["view_count"] == before + 1
    assert stats["student_viewers_30d"] >= 1


async def test_interest_is_idempotent_and_shows_on_the_map(client, make_member):
    _, student = await make_member(role="student", level=1)
    sid = await startup_id(client, student, "LedgerLoop")
    stats = (await client.get(f"/api/startups/{sid}/stats", headers=student)).json()
    assert stats["you_are_interested"] is False
    first = (await client.post(f"/api/startups/{sid}/interest", headers=student)).json()
    second = (await client.post(f"/api/startups/{sid}/interest", headers=student)).json()
    assert first["interested"] and second["interest_count"] == first["interest_count"]
    stats = (await client.get(f"/api/startups/{sid}/stats", headers=student)).json()
    assert stats["you_are_interested"] is True

    r = await client.get(
        "/api/map/startups/nearby",
        headers=student,
        params={"lat": 12.9716, "lng": 77.5946, "radius_km": 30},
    )
    pin = next(p for p in r.json()["items"] if p["id"] == sid)
    assert pin["interested"] is True and pin["interest_count"] == first["interest_count"]


async def test_unclaimed_startup_shows_student_interest(client, login):
    headers = await login("ravi")
    sid = await startup_id(client, headers, "TerraGrid")
    stats = (await client.get(f"/api/startups/{sid}/stats", headers=headers)).json()
    assert stats["interested_students"] >= 14 and stats["view_count"] >= 63


# --- claiming ------------------------------------------------------------------------------


async def test_rohan_claims_terragrid(client, login, terragrid_unclaimed):
    rohan = await login("rohan")
    sid = await startup_id(client, rohan, "TerraGrid")
    # Before claiming, he can't see who is interested or edit the page.
    assert (await client.get(f"/api/startups/{sid}/interested", headers=rohan)).status_code == 403

    r = await client.post(
        f"/api/startups/{sid}/claim", headers=rohan, json={"email": "rohan@terragrid.example"}
    )
    assert r.status_code == 201, r.text
    claim = r.json()
    assert claim["sent_to_domain"] == "terragrid.example" and len(claim["dev_code"]) == 6

    r = await client.post(
        f"/api/startups/{sid}/claim/verify",
        headers=rohan,
        json={"claim_id": claim["claim_id"], "code": claim["dev_code"]},
    )
    assert r.status_code == 200, r.text
    assert (
        r.json()["claimed_by_member_id"]
        == (await client.get("/api/members/me", headers=rohan)).json()["id"]
    )

    interested = (await client.get(f"/api/startups/{sid}/interested", headers=rohan)).json()
    assert len(interested) >= 14 and all(m["role"] == "student" for m in interested)
    edit = await client.patch(f"/api/startups/{sid}", headers=rohan, json={"hiring": True})
    assert edit.status_code == 200

    # Nobody else can claim it now.
    meera = await login("meera")
    again = await client.post(
        f"/api/startups/{sid}/claim", headers=meera, json={"email": "meera@terragrid.example"}
    )
    assert again.status_code == 409


@pytest.mark.parametrize(
    "email",
    [
        "rohan@gmail.com",
        "rohan@terragrid.example.evil.com",
        "not-an-email",
        "rohan@notterragrid.example",
    ],
)
async def test_claim_needs_an_email_on_the_startups_domain(
    client, login, terragrid_unclaimed, email
):
    rohan = await login("rohan")
    sid = await startup_id(client, rohan, "TerraGrid")
    r = await client.post(f"/api/startups/{sid}/claim", headers=rohan, json={"email": email})
    assert r.status_code == 422


async def test_subdomain_email_is_accepted(client, login, terragrid_unclaimed):
    rohan = await login("rohan")
    sid = await startup_id(client, rohan, "TerraGrid")
    r = await client.post(
        f"/api/startups/{sid}/claim", headers=rohan, json={"email": "r@mail.terragrid.example"}
    )
    assert r.status_code == 201


async def test_only_founders_claim(client, login, terragrid_unclaimed):
    ravi = await login("ravi")
    sid = await startup_id(client, ravi, "TerraGrid")
    r = await client.post(
        f"/api/startups/{sid}/claim", headers=ravi, json={"email": "r@terragrid.example"}
    )
    assert r.status_code == 403


async def test_wrong_codes_lock_the_claim(client, login, terragrid_unclaimed):
    rohan = await login("rohan")
    sid = await startup_id(client, rohan, "TerraGrid")
    claim = (
        await client.post(
            f"/api/startups/{sid}/claim", headers=rohan, json={"email": "r@terragrid.example"}
        )
    ).json()
    wrong = "000000" if claim["dev_code"] != "000000" else "111111"
    for _ in range(5):
        r = await client.post(
            f"/api/startups/{sid}/claim/verify",
            headers=rohan,
            json={"claim_id": claim["claim_id"], "code": wrong},
        )
        assert r.status_code == 422
    # Even the right code no longer works.
    r = await client.post(
        f"/api/startups/{sid}/claim/verify",
        headers=rohan,
        json={"claim_id": claim["claim_id"], "code": claim["dev_code"]},
    )
    assert r.status_code == 404


async def test_a_new_code_replaces_the_old_one(client, login, terragrid_unclaimed):
    rohan = await login("rohan")
    sid = await startup_id(client, rohan, "TerraGrid")
    old = (
        await client.post(
            f"/api/startups/{sid}/claim", headers=rohan, json={"email": "r@terragrid.example"}
        )
    ).json()
    await client.post(
        f"/api/startups/{sid}/claim", headers=rohan, json={"email": "r@terragrid.example"}
    )
    r = await client.post(
        f"/api/startups/{sid}/claim/verify",
        headers=rohan,
        json={"claim_id": old["claim_id"], "code": old["dev_code"]},
    )
    assert r.status_code == 404


async def test_someone_elses_claim_cannot_be_verified(
    client, login, make_member, terragrid_unclaimed
):
    rohan = await login("rohan")
    sid = await startup_id(client, rohan, "TerraGrid")
    claim = (
        await client.post(
            f"/api/startups/{sid}/claim", headers=rohan, json={"email": "r@terragrid.example"}
        )
    ).json()
    _, other = await make_member(role="founder", level=1)
    r = await client.post(
        f"/api/startups/{sid}/claim/verify",
        headers=other,
        json={"claim_id": claim["claim_id"], "code": claim["dev_code"]},
    )
    assert r.status_code == 404


async def test_public_demo_deployment_simulates_the_email(terragrid_unclaimed, seeded):
    settings = make_test_settings(env="production", demo_public=True, demo_jwt_secret="y" * 40)
    app = create_app(settings)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/api/auth/demo/login", json={"persona": "rohan"})
        headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
        sid = await startup_id(c, headers, "TerraGrid")
        r = await c.post(
            f"/api/startups/{sid}/claim", headers=headers, json={"email": "r@terragrid.example"}
        )
        assert r.status_code == 201 and r.json()["dev_code"]


def test_real_production_never_shows_the_code():
    from app.claims import EmailNotConfigured, send_claim_code

    with pytest.raises(EmailNotConfigured):
        send_claim_code(
            make_test_settings(env="production", demo_auth=False), "a@b.example", "B", "123456"
        )


def test_dev_code_only_outside_production_or_in_public_demo():
    from app.claims import can_show_dev_code

    assert can_show_dev_code(make_test_settings(env="development"))
    assert not can_show_dev_code(make_test_settings(env="production", demo_auth=False))
    assert can_show_dev_code(
        make_test_settings(env="production", demo_public=True, demo_jwt_secret="z" * 40)
    )
