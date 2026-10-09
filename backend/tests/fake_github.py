"""A fake GitHub for tests: OAuth and the API endpoints the importer calls.

Plug it in with httpx.MockTransport(fake.handler). Nothing here touches the network.
"""

import json
import random
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs

import httpx

API = "https://api.github.com"
OAUTH = "https://github.com"


def iso(days_ago: float) -> str:
    return (datetime.now(UTC) - timedelta(days=days_ago)).isoformat().replace("+00:00", "Z")


@dataclass
class FakeAccount:
    login: str
    id: int = field(default_factory=lambda: random.randint(10**8, 10**9))
    blog: str = ""
    repos: list[dict] = field(default_factory=list)
    languages: dict[str, dict] = field(default_factory=dict)  # full_name -> {lang: bytes}
    contributors: dict[str, list] = field(default_factory=dict)
    readmes: dict[str, str] = field(default_factory=dict)
    prs: list[dict] = field(default_factory=list)
    events: list[dict] = field(default_factory=list)


class FakeGitHub:
    def __init__(self):
        self.codes: dict[str, str] = {}  # one-time code -> token
        self.tokens: dict[str, FakeAccount] = {}
        self.calls: list[str] = []
        self.revoked: list[str] = []
        # Rate limit: after this many API calls, answer 403 with remaining=0.
        self.rate_limit_after: int | None = None
        self.rate_limit_reset = datetime.now(UTC) + timedelta(minutes=30)
        self.secondary_limit = False

    # --- building accounts --------------------------------------------------------------

    def account(self, login: str, **kw) -> FakeAccount:
        return FakeAccount(login=login, **kw)

    def authorise(self, account: FakeAccount, code: str | None = None) -> str:
        """The student approves on GitHub: returns the code GitHub would redirect with."""
        code = code or f"code-{random.randint(0, 10**9)}"
        token = f"gho_{random.randint(0, 10**12)}"
        self.codes[code] = token
        self.tokens[token] = account
        return code

    def add_repo(
        self,
        account: FakeAccount,
        name: str,
        *,
        owner_id: int | None = None,
        fork: bool = False,
        languages: dict | None = None,
        my_commits: int = 10,
        other_commits: int = 0,
        readme: str = "",
        topics: list[str] | None = None,
        stars: int = 0,
        homepage: str | None = None,
    ) -> dict:
        full = f"{account.login}/{name}"
        repo = {
            "id": random.randint(10**8, 10**9),
            "name": name,
            "full_name": full,
            "fork": fork,
            "owner": {"id": owner_id or account.id, "login": account.login},
            "html_url": f"https://github.com/{full}",
            "description": f"{name} description",
            "homepage": homepage,
            "language": next(iter(languages or {}), None),
            "topics": topics or [],
            "stargazers_count": stars,
            "pushed_at": iso(2),
        }
        account.repos.append(repo)
        account.languages[full] = languages or {}
        account.contributors[full] = [
            {"id": account.id, "login": account.login, "contributions": my_commits},
            *(
                [{"id": 1, "login": "someone", "contributions": other_commits}]
                if other_commits
                else []
            ),
        ]
        account.readmes[full] = readme
        return repo

    # --- the transport ------------------------------------------------------------------

    def _json(self, data, status=200, headers=None):
        return httpx.Response(status, json=data, headers=headers)

    def handler(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        self.calls.append(f"{request.method} {request.url.path}")
        if url.startswith(f"{OAUTH}/login/oauth/access_token"):
            body = parse_qs(request.content.decode())
            token = self.codes.pop(body.get("code", [""])[0], None)
            if token is None:
                return self._json({"error": "bad_verification_code"})
            return self._json({"access_token": token, "scope": "", "token_type": "bearer"})
        if request.method == "DELETE" and "/grant" in url:
            self.revoked.append(json.loads(request.content)["access_token"])
            return httpx.Response(204)

        api_calls = sum(1 for c in self.calls if not c.startswith("POST /login"))
        if self.rate_limit_after is not None and api_calls > self.rate_limit_after:
            headers = (
                {"retry-after": "60"}
                if self.secondary_limit
                else {
                    "x-ratelimit-remaining": "0",
                    "x-ratelimit-reset": str(int(self.rate_limit_reset.timestamp())),
                }
            )
            return self._json({"message": "API rate limit exceeded"}, 403, headers)

        auth = request.headers.get("authorization", "")
        account = self.tokens.get(auth.removeprefix("Bearer "))
        if account is None:
            return self._json({"message": "Bad credentials"}, 401)
        path = request.url.path
        if path == "/user":
            return self._json(
                {
                    "id": account.id,
                    "login": account.login,
                    "html_url": f"https://github.com/{account.login}",
                    "blog": account.blog,
                    "followers": 9999,
                }
            )
        if path == f"/users/{account.login}/repos":
            return self._json(account.repos)
        if path == f"/users/{account.login}/events/public":
            return self._json(account.events)
        if path == "/search/issues":
            return self._json({"total_count": len(account.prs), "items": account.prs})
        if path.startswith("/repos/"):
            parts = path.split("/")
            full, what = f"{parts[2]}/{parts[3]}", parts[4]
            if what == "languages":
                return self._json(account.languages.get(full, {}))
            if what == "contributors":
                return self._json(account.contributors.get(full, []))
            if what == "readme":
                text = account.readmes.get(full, "")
                return httpx.Response(200, text=text) if text else self._json({}, 404)
        return self._json({"message": "Not Found"}, 404)
