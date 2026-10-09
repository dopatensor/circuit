"""GitHub proof of work (R2): OAuth connect, import, refresh, rate limits, disconnect.

GitHub is always the fake in tests/fake_github.py: no live API calls.
"""

import uuid
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.proof import get_github_transport
from app.db import get_sessionmaker, make_engine
from app.github import service
from app.main import create_app
from app.models import GitHubAccount, GitHubRepo, Member
from tests.conftest import make_test_settings
from tests.fake_github import FakeGitHub, iso

pytestmark = pytest.mark.anyio


@pytest.fixture
def fake() -> FakeGitHub:
    return FakeGitHub()


@pytest.fixture
def gh_settings():
    return make_test_settings(github_client_id="cid-123", github_client_secret="secret-xyz")


@pytest.fixture
async def gh_client(gh_settings, fake, seeded):
    app = create_app(gh_settings)
    app.dependency_overrides[get_github_transport] = lambda: httpx.MockTransport(fake.handler)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    from app.db import get_engine

    await get_engine().dispose()


@pytest.fixture
async def db(seeded):
    engine = make_engine(seeded)
    async with AsyncSession(engine, expire_on_commit=False) as s:
        yield s
    await engine.dispose()


def a_coder(fake: FakeGitHub, login: str | None = None):
    """An account with: two original repos, a fork, a repo owned by someone else, one
    repo with too few of their commits, merged PRs and recent activity."""
    acc = fake.account(login or f"dev{uuid.uuid4().hex[:6]}", blog="devsite.example")
    fake.add_repo(
        acc, "invoice-api", languages={"Python": 9000, "Dockerfile": 300},
        my_commits=40, readme="# Invoice API\n![badge](x.svg)\nA **FastAPI** service on Postgres.",
        topics=["fastapi", "docker"], homepage="https://invoice.example",
    )  # fmt: skip
    fake.add_repo(
        acc, "shop-ui", languages={"TypeScript": 8000, "CSS": 2000}, my_commits=25,
        other_commits=5, topics=["react"], stars=5000,
    )  # fmt: skip
    fake.add_repo(acc, "forked-lib", fork=True, languages={"Go": 9000}, my_commits=50)
    fake.add_repo(acc, "org-repo", owner_id=42, languages={"Rust": 9000}, my_commits=50)
    fake.add_repo(acc, "tiny", languages={"Kotlin": 500}, my_commits=2)
    acc.prs = [
        {
            "repository_url": "https://api.github.com/repos/pallets/flask",
            "html_url": "https://github.com/pallets/flask/pull/1",
            "pull_request": {"merged_at": iso(10)},
        },
        {  # their own repo: not "external"
            "repository_url": f"https://api.github.com/repos/{acc.login}/invoice-api",
            "html_url": "https://github.com/x/y/pull/2",
            "pull_request": {"merged_at": iso(5)},
        },
    ]
    acc.events = [
        {"type": "PushEvent", "created_at": iso(1)},
        {"type": "PushEvent", "created_at": iso(15)},
        {"type": "WatchEvent", "created_at": iso(2)},  # starring isn't activity
        {"type": "PushEvent", "created_at": iso(200)},  # too old
    ]
    return acc


async def connect(client, fake, headers, account):
    start = await client.post("/api/proof/github/start", headers=headers)
    assert start.status_code == 200, start.text
    state = parse_qs(urlparse(start.json()["authorize_url"]).query)["state"][0]
    code = fake.authorise(account)
    return await client.post(
        "/api/proof/github/finish", headers=headers, json={"code": code, "state": state}
    )


# --- OAuth --------------------------------------------------------------------------------


async def test_connect_is_off_without_an_oauth_app(client, make_member):
    _, headers = await make_member(role="student", level=1)
    r = await client.post("/api/proof/github/start", headers=headers)
    assert r.status_code == 503
    assert "isn't set up" in r.json()["detail"]
    me = (await client.get("/api/proof/me", headers=headers)).json()
    assert me["github_available"] is False and me["github"] is None


async def test_start_asks_for_no_scopes_and_only_students_connect(gh_client, make_member):
    _, headers = await make_member(role="student", level=1)
    r = await gh_client.post("/api/proof/github/start", headers=headers)
    url = urlparse(r.json()["authorize_url"])
    query = parse_qs(url.query)
    assert url.netloc == "github.com" and url.path == "/login/oauth/authorize"
    assert "scope" not in query  # no scopes: read-only access to public data
    assert query["client_id"] == ["cid-123"] and query["state"]

    _, founder = await make_member(role="founder", level=1)
    assert (await gh_client.post("/api/proof/github/start", headers=founder)).status_code == 403


async def test_connect_imports_original_repos_only(gh_client, fake, make_member, db):
    member_id, headers = await make_member(role="student", level=1)
    acc = a_coder(fake)
    r = await connect(gh_client, fake, headers, acc)
    assert r.status_code == 200, r.text
    assert r.json()["login"] == acc.login

    me = (await gh_client.get("/api/proof/me", headers=headers)).json()["github"]
    assert me["status"] == "ok", me  # the background import ran
    names = {repo["name"] for repo in me["repos"]}
    assert names == {"invoice-api", "shop-ui", "tiny"}  # no fork, no repo owned by others
    caps = {v["capability_id"]: v for v in me["verified_capabilities"]}
    assert set(caps) == {"backend_development", "devops_cloud", "frontend_development"}
    assert "FastAPI" in caps["backend_development"]["evidence"]
    assert "mobile_development" not in caps  # "tiny" has too few of their commits
    assert me["external_prs_total"] == 1 and me["external_prs"][0]["repo"] == "pallets/flask"
    assert me["active_weeks_90d"] == 2
    assert me["homepage_url"] == "https://devsite.example"
    invoice = next(x for x in me["repos"] if x["name"] == "invoice-api")
    assert invoice["readme_excerpt"] == "Invoice API A FastAPI service on Postgres."
    assert invoice["homepage_url"] == "https://invoice.example"
    assert "stars" not in str(me).lower() and "followers" not in str(me).lower()
    assert all(not x["featured"] for x in me["repos"])  # the student picks

    # The token is stored encrypted, never returned.
    stored = await db.get(GitHubAccount, member_id)
    token = next(t for t, a in fake.tokens.items() if a is acc)
    assert stored.access_token_enc and token not in stored.access_token_enc
    assert token not in str(me)
    settings = make_test_settings(github_client_secret="secret-xyz")
    assert service.decrypt_token(settings, stored.access_token_enc) == token


async def test_state_must_belong_to_the_signed_in_student(gh_client, fake, make_member):
    _, alice = await make_member(role="student", level=1)
    _, bob = await make_member(role="student", level=1)
    start = await gh_client.post("/api/proof/github/start", headers=alice)
    state = parse_qs(urlparse(start.json()["authorize_url"]).query)["state"][0]
    code = fake.authorise(a_coder(fake))
    # Bob can't finish a connection Alice started (and neither can a forged state).
    r = await gh_client.post(
        "/api/proof/github/finish", headers=bob, json={"code": code, "state": state}
    )
    assert r.status_code == 400
    r = await gh_client.post(
        "/api/proof/github/finish", headers=alice, json={"code": code, "state": "forged"}
    )
    assert r.status_code == 400


async def test_one_github_account_links_to_one_profile(gh_client, fake, make_member):
    _, alice = await make_member(role="student", level=1)
    _, bob = await make_member(role="student", level=1)
    acc = a_coder(fake)
    assert (await connect(gh_client, fake, alice, acc)).status_code == 200
    r = await connect(gh_client, fake, bob, acc)
    assert r.status_code == 409
    assert "already linked" in r.json()["detail"]


async def test_bad_code_is_refused(gh_client, fake, make_member):
    _, headers = await make_member(role="student", level=1)
    start = await gh_client.post("/api/proof/github/start", headers=headers)
    state = parse_qs(urlparse(start.json()["authorize_url"]).query)["state"][0]
    r = await gh_client.post(
        "/api/proof/github/finish", headers=headers, json={"code": "used", "state": state}
    )
    assert r.status_code == 502


async def test_typed_usernames_are_never_verified(gh_client, fake, make_member):
    member_id, headers = await make_member(role="student", level=1)
    # There is no way to give us a username: the finish endpoint needs GitHub's code.
    r = await gh_client.post(
        "/api/proof/github/finish", headers=headers, json={"login": "torvalds"}
    )
    assert r.status_code == 422
    r = await gh_client.patch("/api/members/me", headers=headers, json={"github": "torvalds"})
    assert r.status_code == 200
    # A GitHub link added as proof stays a plain link: no account, no verified skills.
    r = await gh_client.post(
        "/api/proof/items",
        headers=headers,
        json={
            "url": "https://github.com/torvalds/linux",
            "title": "Linux",
            "description": "I wrote this, honestly, all of it, every line.",
            "capability_ids": ["embedded_hardware"],
        },
    )
    assert r.status_code == 201 and r.json()["kind"] == "code"
    proof = (await gh_client.get("/api/proof/me", headers=headers)).json()
    assert proof["github"] is None
    public = (await gh_client.get(f"/api/members/{member_id}", headers=headers)).json()
    assert public["proof"]["github"] is None


# --- featuring and hiding -----------------------------------------------------------------


async def test_feature_and_hide_repos(gh_client, fake, make_member):
    member_id, headers = await make_member(role="student", level=1)
    await connect(gh_client, fake, headers, a_coder(fake))
    repos = (await gh_client.get("/api/proof/me", headers=headers)).json()["github"]["repos"]
    by = {r["name"]: r["id"] for r in repos}

    r = await gh_client.patch(
        f"/api/proof/github/repos/{by['invoice-api']}", headers=headers, json={"featured": True}
    )
    assert r.json()["featured"] is True
    public = (await gh_client.get(f"/api/members/{member_id}", headers=headers)).json()
    assert [x["name"] for x in public["proof"]["github"]["featured_repos"]] == ["invoice-api"]

    # Hiding unfeatures it, takes it off the profile and out of verified skills.
    r = await gh_client.patch(
        f"/api/proof/github/repos/{by['invoice-api']}", headers=headers, json={"hidden": True}
    )
    assert r.json()["hidden"] and not r.json()["featured"]
    github = (await gh_client.get(f"/api/members/{member_id}", headers=headers)).json()["proof"][
        "github"
    ]
    assert github["featured_repos"] == []
    caps = {v["capability_id"] for v in github["verified_capabilities"]}
    assert caps == {"frontend_development"}
    r = await gh_client.patch(
        f"/api/proof/github/repos/{by['invoice-api']}", headers=headers, json={"featured": True}
    )
    assert r.status_code == 409

    # Someone else's repo: not found.
    _, other = await make_member(role="student", level=1)
    r = await gh_client.patch(
        f"/api/proof/github/repos/{by['shop-ui']}", headers=other, json={"hidden": True}
    )
    assert r.status_code == 404


async def test_at_most_six_featured(gh_client, fake, make_member):
    _, headers = await make_member(role="student", level=1)
    acc = fake.account(f"many{uuid.uuid4().hex[:6]}")
    for i in range(7):
        fake.add_repo(acc, f"repo{i}", languages={"Python": 100}, my_commits=5)
    await connect(gh_client, fake, headers, acc)
    repos = (await gh_client.get("/api/proof/me", headers=headers)).json()["github"]["repos"]
    codes = [
        (
            await gh_client.patch(
                f"/api/proof/github/repos/{r['id']}", headers=headers, json={"featured": True}
            )
        ).status_code
        for r in repos
    ]
    assert codes == [200] * 6 + [409]


# --- disconnect ---------------------------------------------------------------------------


async def test_disconnect_deletes_all_imported_data(gh_client, fake, make_member, db):
    member_id, headers = await make_member(role="student", level=1)
    acc = a_coder(fake)
    await connect(gh_client, fake, headers, acc)
    assert await db.scalar(select(func.count()).where(GitHubRepo.member_id == member_id)) == 3

    r = await gh_client.delete("/api/proof/github", headers=headers)
    assert r.status_code == 204
    assert await db.get(GitHubAccount, member_id) is None
    assert await db.scalar(select(func.count()).where(GitHubRepo.member_id == member_id)) == 0
    assert len(fake.revoked) == 1  # and GitHub was asked to forget the grant
    me = (await gh_client.get("/api/proof/me", headers=headers)).json()
    assert me["github"] is None
    assert (await gh_client.delete("/api/proof/github", headers=headers)).status_code == 404
    # The same GitHub account can now be linked again (to anyone).
    assert (await connect(gh_client, fake, headers, acc)).status_code == 200


async def test_deleting_a_profile_deletes_github_data(gh_client, fake, make_member, db):
    member_id, headers = await make_member(role="student", level=1)
    await connect(gh_client, fake, headers, a_coder(fake))
    assert (await gh_client.delete("/api/members/me", headers=headers)).status_code == 204
    assert await db.get(Member, member_id) is None
    assert await db.get(GitHubAccount, member_id) is None
    assert await db.scalar(select(func.count()).where(GitHubRepo.member_id == member_id)) == 0


# --- import failures and the weekly refresh -----------------------------------------------


async def _connected(gh_client, fake, make_member):
    member_id, headers = await make_member(role="student", level=1)
    acc = a_coder(fake)
    await connect(gh_client, fake, headers, acc)
    return member_id, headers, acc


async def _make_due(db, member_id):
    account = await db.get(GitHubAccount, member_id)
    account.next_fetch_at = datetime.now(UTC) - timedelta(minutes=1)
    await db.commit()


async def test_rate_limit_keeps_old_data_and_waits_for_reset(
    gh_client, fake, make_member, db, gh_settings
):
    member_id, headers, acc = await _connected(gh_client, fake, make_member)
    fake.add_repo(acc, "new-repo", languages={"Go": 5000}, my_commits=9)
    await _make_due(db, member_id)
    fake.calls.clear()
    fake.rate_limit_after = 4  # fails part-way through the repos

    transport = httpx.MockTransport(fake.handler)
    done = await service.refresh_due(get_sessionmaker(), gh_settings, transport)
    assert done >= 1
    me = (await gh_client.get("/api/proof/me", headers=headers)).json()["github"]
    assert me["status"] == "rate_limited"
    assert "slow down" in me["status_message"]
    assert {r["name"] for r in me["repos"]} == {"invoice-api", "shop-ui", "tiny"}  # untouched
    next_fetch = datetime.fromisoformat(me["next_fetch_at"])
    assert next_fetch >= fake.rate_limit_reset  # waits for GitHub's reset time

    # Once the limit resets, the next run picks it up and imports the new repo.
    fake.rate_limit_after = None
    await _make_due(db, member_id)
    await service.refresh_due(get_sessionmaker(), gh_settings, transport)
    me = (await gh_client.get("/api/proof/me", headers=headers)).json()["github"]
    assert me["status"] == "ok" and "new-repo" in {r["name"] for r in me["repos"]}
    assert datetime.fromisoformat(me["next_fetch_at"]) > datetime.now(UTC) + timedelta(days=6)


async def test_secondary_rate_limit_uses_retry_after(gh_client, fake, make_member, db, gh_settings):
    member_id, headers, _ = await _connected(gh_client, fake, make_member)
    await _make_due(db, member_id)
    fake.rate_limit_after, fake.secondary_limit = 0, True
    async with get_sessionmaker()() as s, s.begin():
        status = await service.import_account(
            s, gh_settings, member_id, httpx.MockTransport(fake.handler)
        )
    assert status == "rate_limited"
    account = await db.get(GitHubAccount, member_id)
    await db.refresh(account)
    wait = account.next_fetch_at - datetime.now(UTC)
    assert timedelta(seconds=60) < wait < timedelta(minutes=3)


async def test_revoked_token_asks_to_reconnect(gh_client, fake, make_member, db, gh_settings):
    member_id, headers, acc = await _connected(gh_client, fake, make_member)
    fake.tokens.clear()  # the student removed our app on GitHub
    await _make_due(db, member_id)
    await service.refresh_due(get_sessionmaker(), gh_settings, httpx.MockTransport(fake.handler))
    me = (await gh_client.get("/api/proof/me", headers=headers)).json()["github"]
    assert me["status"] == "error" and me["next_fetch_at"] is None
    assert "Connect again" in me["status_message"]
    assert len(me["repos"]) == 3  # still shown until they reconnect or disconnect


async def test_github_outage_retries_within_the_hour(gh_client, fake, make_member, db, gh_settings):
    member_id, headers, _ = await _connected(gh_client, fake, make_member)
    await _make_due(db, member_id)

    def down(request):
        return httpx.Response(502)

    await service.refresh_due(get_sessionmaker(), gh_settings, httpx.MockTransport(down))
    me = (await gh_client.get("/api/proof/me", headers=headers)).json()["github"]
    assert me["status"] == "error"
    wait = datetime.fromisoformat(me["next_fetch_at"]) - datetime.now(UTC)
    assert timedelta(minutes=50) < wait <= timedelta(hours=1)


async def test_seeded_accounts_are_never_refreshed(fake, gh_settings, db, seeded):
    # Ravi's GitHub data is saved in the seed (no token), so demos never call GitHub.
    calls_before = len(fake.calls)
    await service.refresh_due(get_sessionmaker(), gh_settings, httpx.MockTransport(fake.handler))
    assert len(fake.calls) == calls_before
    ravi = await db.scalar(select(GitHubAccount).where(GitHubAccount.login == "ravi-kumar"))
    assert ravi.source == "seed" and ravi.access_token_enc is None


async def test_page_views_never_call_github(gh_client, fake, login):
    headers = await login("ravi")
    fake.calls.clear()
    me = (await gh_client.get("/api/members/me", headers=headers)).json()
    assert me["proof"]["github"]["login"] == "ravi-kumar"
    await gh_client.get("/api/proof/me", headers=headers)
    assert fake.calls == []
