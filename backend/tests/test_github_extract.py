"""Pure GitHub extraction: what counts as proof and how it maps to capabilities."""

from datetime import UTC, datetime, timedelta

import httpx

from app.github import extract
from app.github.client import RateLimited, TokenRevoked, raise_for_github, rate_limit_reset

ME = 1001


def repo(name="r", *, owner=ME, fork=False, **kw):
    return {"id": hash(name) % 10**6, "name": name, "html_url": f"https://github.com/me/{name}",
            "owner": {"id": owner}, "fork": fork, **kw}  # fmt: skip


def facts(name="r", languages=None, frameworks=(), mine=10, total=None):
    return extract.RepoFacts(
        github_repo_id=hash(name) % 10**6, name=name, html_url="", description="",
        homepage_url=None, primary_language=None, languages=languages or {},
        frameworks=list(frameworks), commits_by_user=mine, commits_total=total or mine,
        readme_excerpt="", pushed_at=None,
    )  # fmt: skip


def test_forks_and_repos_owned_by_others_are_excluded():
    repos = [repo("mine"), repo("fork", fork=True), repo("org", owner=42), repo("x", owner=None)]
    assert [r["name"] for r in extract.original_repos(repos, ME)] == ["mine"]


def test_ownership_is_by_account_id_not_name():
    # A repo listed under the same login but owned by a different account id is out.
    impostor = repo("lookalike", owner=ME + 1)
    impostor["owner"]["login"] = "me"
    assert extract.original_repos([impostor], ME) == []


def test_commit_counts():
    contributors = [{"id": ME, "contributions": 12}, {"id": 7, "contributions": 3}]
    assert extract.commit_counts(contributors, ME) == (12, 15)
    assert extract.commit_counts([], ME) == (0, 0)


def test_capabilities_need_the_students_own_commits():
    few = facts("few", {"Python": 100}, mine=extract.MIN_USER_COMMITS - 1)
    enough = facts("enough", {"Kotlin": 100}, mine=extract.MIN_USER_COMMITS)
    caps = [v.capability_id for v in extract.verified_capabilities([few, enough])]
    assert caps == ["mobile_development"]


def test_small_languages_dont_count_but_frameworks_do():
    r = facts("api", {"Python": 900, "Dockerfile": 50, "Shell": 50}, frameworks=["Docker"])
    found = {v.capability_id: v.evidence for v in extract.verified_capabilities([r])}
    assert found == {"backend_development": ["Python"], "devops_cloud": ["Docker"]}


def test_verified_capabilities_count_repos():
    a = facts("a", {"TypeScript": 100}, frameworks=["React"])
    b = facts("b", {"CSS": 100})
    c = facts("c", {"Go": 100})
    out = extract.verified_capabilities([a, b, c])
    assert out[0].capability_id == "frontend_development" and out[0].repo_count == 2
    assert out[0].evidence == ["TypeScript", "React", "CSS"]


def test_stars_are_ignored():
    plain = repo("p", language="Python")
    famous = repo("p", language="Python", stargazers_count=100_000, watchers_count=5000)
    a = extract.repo_facts(plain, {"Python": 10}, [{"id": ME, "contributions": 5}], "", ME)
    b = extract.repo_facts(famous, {"Python": 10}, [{"id": ME, "contributions": 5}], "", ME)
    assert a == b


def test_detect_frameworks_whole_words_only():
    assert extract.detect_frameworks(["fastapi"], "", "Uses pandas and Docker") == [
        "FastAPI", "pandas", "Docker",
    ]  # fmt: skip
    assert extract.detect_frameworks([], "Expressive poetry generator", "") == []
    assert "React Native" in extract.detect_frameworks(["react-native"], "", "")


def test_readme_excerpt_strips_markup():
    raw = (
        "# Title\n[![CI](badge.svg)](ci)\n<p align='center'>Hi</p>\n"
        "A [link](http://x) and `code`.\n```\nsecret code block\n```\nEnd."
    )
    assert extract.readme_excerpt(raw) == "Title Hi A link and code. End."
    long = "word " * 200
    out = extract.readme_excerpt(long)
    assert len(out) <= extract.README_EXCERPT_CHARS + 1 and out.endswith("…")


def test_clean_url():
    assert extract.clean_url("example.com") == "https://example.com"
    assert extract.clean_url("http://a.example/x") == "http://a.example/x"
    assert extract.clean_url("") is None
    assert extract.clean_url("javascript:alert(1)") is None


def test_external_prs_skip_own_repos_and_unmerged():
    items = [
        {"repository_url": "https://api.github.com/repos/django/django",
         "html_url": "u1", "pull_request": {"merged_at": "2026-09-01T00:00:00Z"}},
        {"repository_url": "https://api.github.com/repos/Me/thing",
         "html_url": "u2", "pull_request": {"merged_at": "2026-09-01T00:00:00Z"}},
        {"repository_url": "https://api.github.com/repos/x/y",
         "html_url": "u3", "pull_request": {"merged_at": None}},
    ]  # fmt: skip
    out = extract.external_prs(3, items, "me")
    assert out.total == 1 and [p["repo"] for p in out.items] == ["django/django"]


def test_activity_counts_weeks_with_pushes_or_prs():
    now = datetime(2026, 10, 9, tzinfo=UTC)

    def ev(t, days):
        return {"type": t, "created_at": (now - timedelta(days=days)).isoformat()}

    events = [ev("PushEvent", 1), ev("PushEvent", 1.5), ev("PullRequestEvent", 20),
              ev("WatchEvent", 3), ev("PushEvent", 120)]  # fmt: skip
    act = extract.activity(events, now)
    assert act.active_weeks == 2
    assert act.last_active_at == now - timedelta(days=1)


# --- client error handling ------------------------------------------------------------------


def test_rate_limit_detection():
    reset = datetime(2026, 10, 9, 12, tzinfo=UTC)
    primary = httpx.Response(
        403,
        headers={"x-ratelimit-remaining": "0", "x-ratelimit-reset": str(int(reset.timestamp()))},
    )
    assert rate_limit_reset(primary) == reset
    now = datetime(2026, 10, 9, tzinfo=UTC)
    secondary = httpx.Response(429, headers={"retry-after": "90"})
    assert rate_limit_reset(secondary, now) == now + timedelta(seconds=90)
    assert rate_limit_reset(httpx.Response(403)) is None  # a plain "forbidden"

    for response, error in ((primary, RateLimited), (httpx.Response(401), TokenRevoked)):
        try:
            raise_for_github(response)
        except error:
            pass
        else:
            raise AssertionError(f"{response.status_code} should raise {error.__name__}")
