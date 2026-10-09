"""A small GitHub API client.

Every failure becomes one of a few exceptions with a short code, so the importer can
decide what to do (wait for the rate limit to reset, ask the student to reconnect, or
retry later). Codes are stored in github_accounts.last_error; messages never are.
"""

from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import httpx

from app.config import Settings

USER_AGENT = "circuit-proof-of-work"
API_VERSION = "2022-11-28"


class GitHubError(Exception):
    """Something went wrong talking to GitHub. `code` is safe to store and show."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class RateLimited(GitHubError):
    def __init__(self, reset_at: datetime):
        super().__init__("rate_limited")
        self.reset_at = reset_at


class TokenRevoked(GitHubError):
    """The student revoked our access on GitHub (or the token expired)."""

    def __init__(self):
        super().__init__("token_revoked")


class NotFound(GitHubError):
    def __init__(self):
        super().__init__("not_found")


def rate_limit_reset(response: httpx.Response, now: datetime | None = None) -> datetime | None:
    """When a 403/429 is a rate limit, the time it resets; otherwise None.

    GitHub says so either with x-ratelimit-remaining: 0 (plus x-ratelimit-reset, a Unix
    time) or, for secondary limits, with a retry-after header in seconds."""
    now = now or datetime.now(UTC)
    retry_after = response.headers.get("retry-after")
    if retry_after and retry_after.isdigit():
        return now + timedelta(seconds=int(retry_after))
    if response.headers.get("x-ratelimit-remaining") == "0":
        reset = response.headers.get("x-ratelimit-reset", "")
        if reset.isdigit():
            return datetime.fromtimestamp(int(reset), UTC)
        return now + timedelta(hours=1)
    return None


def raise_for_github(response: httpx.Response) -> None:
    status = response.status_code
    if status < 400:
        return
    if status in (403, 429):
        reset = rate_limit_reset(response)
        if reset is not None:
            raise RateLimited(reset)
        raise GitHubError("forbidden")
    if status == 401:
        raise TokenRevoked()
    if status == 404:
        raise NotFound()
    if status >= 500:
        raise GitHubError("github_unavailable")
    raise GitHubError(f"http_{status}")


def authorize_url(settings: Settings, state: str) -> str:
    """GitHub's consent page. No `scope` parameter: the token can only read public
    data, the smallest access GitHub offers."""
    query = urlencode(
        {
            "client_id": settings.github_client_id,
            "redirect_uri": settings.github_redirect_url,
            "state": state,
            "allow_signup": "false",
        }
    )
    return f"{settings.github_oauth_url}/login/oauth/authorize?{query}"


class GitHubClient:
    """Use as `async with GitHubClient(settings, token) as gh: ...`."""

    def __init__(
        self,
        settings: Settings,
        token: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.settings = settings
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": USER_AGENT,
            "X-GitHub-Api-Version": API_VERSION,
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._http = httpx.AsyncClient(
            base_url=settings.github_api_url,
            headers=headers,
            timeout=settings.github_timeout_s,
            transport=transport,
        )

    async def __aenter__(self) -> "GitHubClient":
        return self

    async def __aexit__(self, *exc) -> None:
        await self._http.aclose()

    async def _get(self, path: str, params: dict | None = None, accept: str | None = None):
        try:
            response = await self._http.get(
                path, params=params, headers={"Accept": accept} if accept else None
            )
        except httpx.HTTPError as exc:
            raise GitHubError("network") from exc
        raise_for_github(response)
        return response

    # --- endpoints ---------------------------------------------------------------------

    async def user(self) -> dict:
        """The account the token belongs to: this is the ownership proof."""
        return (await self._get("/user")).json()

    async def owned_repos(self, login: str, limit: int) -> list[dict]:
        """Public repos the account owns, most recently pushed first."""
        repos: list[dict] = []
        page = 1
        while len(repos) < limit:
            batch = (
                await self._get(
                    f"/users/{login}/repos",
                    {"type": "owner", "sort": "pushed", "per_page": 100, "page": page},
                )
            ).json()
            repos.extend(batch)
            if len(batch) < 100:
                break
            page += 1
        return repos

    async def languages(self, full_name: str) -> dict[str, int]:
        return (await self._get(f"/repos/{full_name}/languages")).json()

    async def contributors(self, full_name: str) -> list[dict]:
        response = await self._get(f"/repos/{full_name}/contributors", {"per_page": 100})
        return [] if response.status_code == 204 else response.json()  # 204: empty repo

    async def readme(self, full_name: str) -> str:
        try:
            response = await self._get(
                f"/repos/{full_name}/readme", accept="application/vnd.github.raw+json"
            )
        except NotFound:
            return ""
        return response.text

    async def merged_external_prs(self, login: str) -> tuple[int, list[dict]]:
        """Merged pull requests the account opened in repos owned by someone else."""
        data = (
            await self._get(
                "/search/issues",
                {
                    "q": f"type:pr author:{login} is:merged -user:{login}",
                    "sort": "updated",
                    "per_page": 20,
                },
            )
        ).json()
        return int(data.get("total_count", 0)), list(data.get("items", []))

    async def public_events(self, login: str) -> list[dict]:
        return (await self._get(f"/users/{login}/events/public", {"per_page": 100})).json()


# --- OAuth -----------------------------------------------------------------------------


async def exchange_code(
    settings: Settings, code: str, transport: httpx.AsyncBaseTransport | None = None
) -> str:
    """Trade the one-time code from GitHub's redirect for an access token."""
    async with httpx.AsyncClient(
        timeout=settings.github_timeout_s,
        transport=transport,
        headers={"Accept": "application/json", "User-Agent": USER_AGENT},
    ) as http:
        try:
            response = await http.post(
                f"{settings.github_oauth_url}/login/oauth/access_token",
                data={
                    "client_id": settings.github_client_id,
                    "client_secret": settings.github_client_secret,
                    "code": code,
                    "redirect_uri": settings.github_redirect_url,
                },
            )
        except httpx.HTTPError as exc:
            raise GitHubError("network") from exc
    raise_for_github(response)
    body = response.json()
    token = body.get("access_token")
    if not token:
        # e.g. {"error": "bad_verification_code"}: the code was used or expired.
        raise GitHubError(str(body.get("error") or "no_token")[:64])
    return token


async def revoke_grant(
    settings: Settings, token: str, transport: httpx.AsyncBaseTransport | None = None
) -> bool:
    """Remove our app from the student's GitHub account. Best effort: disconnecting
    deletes our data whether or not GitHub answers."""
    async with httpx.AsyncClient(
        base_url=settings.github_api_url,
        timeout=settings.github_timeout_s,
        transport=transport,
        auth=(settings.github_client_id or "", settings.github_client_secret or ""),
        headers={"Accept": "application/vnd.github+json", "User-Agent": USER_AGENT},
    ) as http:
        try:
            response = await http.request(
                "DELETE",
                f"/applications/{settings.github_client_id}/grant",
                json={"access_token": token},
            )
        except httpx.HTTPError:
            return False
    return response.status_code == 204
