"""GitHub proof of work: connect, import, refresh, disconnect.

The flow:
1. start_url(): the student is sent to GitHub with a signed `state` naming them.
2. connect(): GitHub sends them back with a code. We check the state belongs to the
   signed-in student, trade the code for a token, and ask GitHub which account the
   token belongs to. That account id is the ownership proof; we never take a
   username from the student.
3. import_account() runs in the background straight after, then weekly
   (refresh_due(), from the scheduler). It writes only when every call succeeded,
   so a rate limit or an outage leaves the last good data in place.
4. disconnect() deletes the account row; imported repos go with it (cascade).
"""

import base64
import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import httpx
import jwt
import structlog
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.events import record_event
from app.github import extract
from app.github.client import (
    GitHubClient,
    GitHubError,
    RateLimited,
    TokenRevoked,
    authorize_url,
    exchange_code,
    revoke_grant,
)
from app.models import GitHubAccount, GitHubRepo

log = structlog.get_logger("github")

STATE_PURPOSE = "github_connect"
STATE_TTL = timedelta(minutes=10)
RETRY_AFTER_ERROR = timedelta(hours=1)
REFRESH_BATCH = 20  # accounts per scheduler run


class ConnectError(Exception):
    """A connect attempt we refuse. `detail` is shown to the student as-is."""

    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status = status
        self.detail = detail


# --- secrets -----------------------------------------------------------------------------


def _cipher(settings: Settings) -> Fernet:
    if settings.github_token_key:
        return Fernet(settings.github_token_key.encode())
    digest = hashlib.sha256(f"circuit-github-token:{settings.github_client_secret}".encode())
    return Fernet(base64.urlsafe_b64encode(digest.digest()))


def encrypt_token(settings: Settings, token: str) -> str:
    return _cipher(settings).encrypt(token.encode()).decode()


def decrypt_token(settings: Settings, value: str) -> str | None:
    try:
        return _cipher(settings).decrypt(value.encode()).decode()
    except (InvalidToken, ValueError):
        return None  # the key changed: the student has to reconnect


def _state_key(settings: Settings) -> str:
    return f"circuit-github-state:{settings.github_client_secret}"


def make_state(settings: Settings, member_id: uuid.UUID) -> str:
    now = datetime.now(UTC)
    claims = {
        "sub": str(member_id),
        "purpose": STATE_PURPOSE,
        "nonce": secrets.token_urlsafe(8),
        "iat": now,
        "exp": now + STATE_TTL,
    }
    return jwt.encode(claims, _state_key(settings), algorithm="HS256")


def read_state(settings: Settings, state: str) -> uuid.UUID | None:
    try:
        claims = jwt.decode(
            state, _state_key(settings), algorithms=["HS256"], options={"require": ["exp", "sub"]}
        )
    except jwt.PyJWTError:
        return None
    if claims.get("purpose") != STATE_PURPOSE:
        return None
    try:
        return uuid.UUID(claims["sub"])
    except ValueError:
        return None


def start_url(settings: Settings, member_id: uuid.UUID) -> str:
    return authorize_url(settings, make_state(settings, member_id))


# --- connect -----------------------------------------------------------------------------


async def connect(
    session: AsyncSession,
    settings: Settings,
    member_id: uuid.UUID,
    code: str,
    state: str,
    transport: httpx.AsyncBaseTransport | None = None,
) -> GitHubAccount:
    """Finish the OAuth round trip. Raises ConnectError for anything we refuse."""
    if read_state(settings, state) != member_id:
        # Expired, tampered with, or started by someone else (a CSRF attempt).
        raise ConnectError(400, "This GitHub link has expired. Start again from your profile.")
    try:
        token = await exchange_code(settings, code, transport)
        async with GitHubClient(settings, token, transport) as gh:
            user = await gh.user()
    except RateLimited as exc:
        raise ConnectError(503, "GitHub is busy right now. Try again in a few minutes.") from exc
    except GitHubError as exc:
        raise ConnectError(502, "GitHub didn't confirm your account. Try again.") from exc

    github_user_id = int(user["id"])
    other = await session.scalar(
        select(GitHubAccount.member_id).where(
            GitHubAccount.github_user_id == github_user_id, GitHubAccount.member_id != member_id
        )
    )
    if other is not None:
        raise ConnectError(409, "That GitHub account is already linked to another profile.")

    existing = await session.get(GitHubAccount, member_id)
    if existing is not None and existing.github_user_id != github_user_id:
        await session.delete(existing)  # a different account: start clean
        await session.flush()
        existing = None
    account = existing or GitHubAccount(member_id=member_id, github_user_id=github_user_id)
    account.login = str(user["login"])[:100]
    account.profile_url = str(user.get("html_url") or f"https://github.com/{user['login']}")[:300]
    account.homepage_url = extract.clean_url(user.get("blog"))
    account.access_token_enc = encrypt_token(settings, token)
    account.source = "oauth"
    account.status = "importing"
    account.last_error = None
    account.next_fetch_at = datetime.now(UTC)
    session.add(account)
    await record_event(
        session,
        "github.connected",
        actor_id=member_id,
        target_type="member",
        target_id=member_id,
        payload={"reconnect": existing is not None},
    )
    return account


# --- import ------------------------------------------------------------------------------


async def fetch_profile(gh: GitHubClient, account: GitHubAccount, settings: Settings):
    """Every GitHub call for one import. Raises before anything is written."""
    user = await gh.user()
    if int(user["id"]) != account.github_user_id:
        raise GitHubError("account_mismatch")  # the token now belongs to someone else
    login = str(user["login"])
    repos = extract.original_repos(
        await gh.owned_repos(login, settings.github_max_repos), account.github_user_id
    )[: settings.github_max_repos]
    facts = []
    for repo in repos:
        full = repo["full_name"]
        facts.append(
            extract.repo_facts(
                repo,
                await gh.languages(full),
                await gh.contributors(full),
                await gh.readme(full),
                account.github_user_id,
            )
        )
    total, items = await gh.merged_external_prs(login)
    prs = extract.external_prs(total, items, login)
    act = extract.activity(await gh.public_events(login))
    return user, facts, prs, act


async def save_profile(session: AsyncSession, account: GitHubAccount, facts, prs, act) -> None:
    """Replace the imported data, keeping the student's featured/hidden choices."""
    keep = [f for f in facts if f.commits_by_user > 0]  # repos with their own commits
    if keep:
        rows = [
            {
                "id": uuid.uuid4(),
                "member_id": account.member_id,
                "github_repo_id": f.github_repo_id,
                "name": f.name,
                "html_url": f.html_url,
                "description": f.description,
                "homepage_url": f.homepage_url,
                "primary_language": f.primary_language,
                "languages": f.languages,
                "frameworks": f.frameworks,
                "commits_by_user": f.commits_by_user,
                "commits_total": f.commits_total,
                "readme_excerpt": f.readme_excerpt,
                "pushed_at": f.pushed_at,
                "featured": False,
                "hidden": False,
            }
            for f in keep
        ]
        stmt = pg_insert(GitHubRepo).values(rows)
        updated = {
            c: getattr(stmt.excluded, c)
            for c in rows[0]
            if c not in ("id", "member_id", "github_repo_id", "featured", "hidden")
        }
        await session.execute(
            stmt.on_conflict_do_update(constraint="uq_github_repos_member_repo", set_=updated)
        )
    await session.execute(
        delete(GitHubRepo).where(
            GitHubRepo.member_id == account.member_id,
            GitHubRepo.github_repo_id.not_in([f.github_repo_id for f in keep] or [-1]),
        )
    )
    account.external_prs = prs.items
    account.external_prs_total = prs.total
    account.active_weeks_90d = act.active_weeks
    account.last_active_at = act.last_active_at


async def import_account(
    session: AsyncSession,
    settings: Settings,
    member_id: uuid.UUID,
    transport: httpx.AsyncBaseTransport | None = None,
) -> str:
    """Fetch and save one student's GitHub profile. Returns the new status.

    Never raises for GitHub problems: they become a status the profile can explain."""
    account = await session.get(GitHubAccount, member_id)
    if account is None or not account.access_token_enc:
        return "skipped"  # disconnected meanwhile, or seeded data with no token
    token = decrypt_token(settings, account.access_token_enc)
    now = datetime.now(UTC)
    error: str | None = None
    try:
        if token is None:
            raise TokenRevoked()
        async with GitHubClient(settings, token, transport) as gh:
            user, facts, prs, act = await fetch_profile(gh, account, settings)
    except RateLimited as exc:
        account.status, account.last_error = "rate_limited", exc.code
        account.next_fetch_at = exc.reset_at + timedelta(minutes=1)
        error = exc.code
    except TokenRevoked as exc:
        account.status, account.last_error = "error", exc.code
        account.next_fetch_at = None  # nothing to retry until they reconnect
        error = exc.code
    except GitHubError as exc:
        account.status, account.last_error = "error", exc.code
        account.next_fetch_at = now + RETRY_AFTER_ERROR
        error = exc.code
    if error:
        log.warning("github_import_failed", member_id=str(member_id), code=error)
        await record_event(
            session, "github.import_failed", actor_id=None, target_type="member",
            target_id=member_id, payload={"code": error},
        )  # fmt: skip
        return account.status

    account.login = str(user["login"])[:100]
    account.profile_url = str(user.get("html_url") or account.profile_url)[:300]
    account.homepage_url = extract.clean_url(user.get("blog"))
    await save_profile(session, account, facts, prs, act)
    account.status, account.last_error = "ok", None
    account.fetched_at = now
    account.next_fetch_at = now + timedelta(days=settings.github_refresh_days)
    proof_repos = sum(1 for f in facts if extract.counts_as_proof(f))
    await record_event(
        session, "github.imported", actor_id=None, target_type="member", target_id=member_id,
        payload={"repos": len(facts), "proof_repos": proof_repos, "external_prs": prs.total},
    )  # fmt: skip
    log.info("github_imported", member_id=str(member_id), repos=len(facts))
    return "ok"


async def refresh_due(
    session_factory, settings: Settings, transport: httpx.AsyncBaseTransport | None = None
) -> int:
    """Import every account whose next fetch is due (weekly, or after a rate limit or
    an error). Each account commits on its own, so one failure doesn't undo others."""
    async with session_factory() as session:
        due = (
            await session.scalars(
                select(GitHubAccount.member_id)
                .where(
                    GitHubAccount.access_token_enc.is_not(None),
                    GitHubAccount.next_fetch_at <= datetime.now(UTC),
                )
                .order_by(GitHubAccount.next_fetch_at)
                .limit(REFRESH_BATCH)
            )
        ).all()
    done = 0
    for member_id in due:
        async with session_factory() as session, session.begin():
            status = await import_account(session, settings, member_id, transport)
        done += 1
        if status == "rate_limited":
            break  # the limit is per app token too; the rest wait for the next run
    return done


# --- disconnect --------------------------------------------------------------------------


async def disconnect(
    session: AsyncSession,
    settings: Settings,
    member_id: uuid.UUID,
    transport: httpx.AsyncBaseTransport | None = None,
) -> bool:
    """Delete the account and every imported repo. Also asks GitHub to forget the
    grant (best effort). Returns False when nothing was connected."""
    account = await session.get(GitHubAccount, member_id)
    if account is None:
        return False
    token = decrypt_token(settings, account.access_token_enc) if account.access_token_enc else None
    await session.execute(delete(GitHubRepo).where(GitHubRepo.member_id == member_id))
    await session.delete(account)
    await record_event(
        session, "github.disconnected", actor_id=member_id, target_type="member",
        target_id=member_id,
    )  # fmt: skip
    if token and settings.github_configured:
        await revoke_grant(settings, token, transport)
    return True
