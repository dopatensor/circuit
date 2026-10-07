"""Authentication (who are you?) and authorisation (what may you do?).

Two kinds of bearer tokens are accepted:

1. Provider tokens (Clerk / Supabase), signed with the provider's private key
   (RS256/ES256). We verify them against the provider's public keys, published at
   JWKS_URL.
2. Demo tokens (only when DEMO_AUTH=true), signed by us with DEMO_JWT_SECRET (HS256)
   for the seeded personas behind the persona switcher.

The token proves *who* you are (its "sub" claim). Your role and verification level
are then read from your member row, so an admin's change takes effect immediately.
The token's own role/verification_level claims only seed a brand-new profile.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Annotated

import anyio
import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db import get_session
from app.models import Member

DEMO_ISSUER = "circuit-demo"
DEMO_SUBJECT_PREFIX = "demo:"
PROVIDER_ALGORITHMS = ["RS256", "ES256"]

# Verification levels (F7)
LEVEL_BROWSE = 1  # email verified: browse startups and people
LEVEL_MATCHES = 2  # work email or LinkedIn: see matches
LEVEL_INTROS = 3  # role verified by an admin: request intros

_bearer = HTTPBearer(auto_error=False)


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status.HTTP_401_UNAUTHORIZED, detail=detail, headers={"WWW-Authenticate": "Bearer"}
    )


@dataclass(frozen=True)
class TokenClaims:
    subject: str
    role: str | None
    verification_level: int | None
    is_demo: bool


# --- issuing demo tokens -----------------------------------------------------------------


def issue_demo_token(settings: Settings, member: Member) -> tuple[str, int]:
    """Sign a short-lived token for a seeded persona. Returns (token, expires_in seconds)."""
    if not settings.demo_auth:
        raise RuntimeError("demo tokens are disabled")
    ttl = settings.demo_token_ttl_minutes * 60
    now = datetime.now(UTC)
    claims = {
        "iss": DEMO_ISSUER,
        "sub": member.auth_subject,
        "role": member.role,
        "verification_level": member.verification_level,
        "iat": now,
        "exp": now + timedelta(seconds=ttl),
    }
    return jwt.encode(claims, settings.demo_jwt_secret, algorithm="HS256"), ttl


# --- verifying tokens --------------------------------------------------------------------


@lru_cache(maxsize=4)
def _jwks_client(url: str) -> jwt.PyJWKClient:
    # Caches the provider's keys, refetching when a token names an unknown key id.
    return jwt.PyJWKClient(url, cache_keys=True, lifespan=3600, timeout=5)


async def decode_token(token: str, settings: Settings) -> TokenClaims:
    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError as exc:
        raise _unauthorized("Malformed token") from exc

    if header.get("alg") == "HS256":
        if not settings.demo_auth:
            raise _unauthorized("Demo tokens are not accepted here")
        try:
            claims = jwt.decode(
                token,
                settings.demo_jwt_secret,
                algorithms=["HS256"],
                issuer=DEMO_ISSUER,
                options={"require": ["exp", "sub", "iss"]},
            )
        except jwt.PyJWTError as exc:
            raise _unauthorized("Invalid or expired token") from exc
        if not str(claims["sub"]).startswith(DEMO_SUBJECT_PREFIX):
            raise _unauthorized("Invalid demo token")
        is_demo = True
    elif header.get("alg") in PROVIDER_ALGORITHMS:
        if not settings.jwks_url:
            raise _unauthorized("Provider tokens are not configured (JWKS_URL is unset)")
        try:
            # PyJWKClient uses blocking HTTP; run it off the event loop.
            key = await anyio.to_thread.run_sync(
                _jwks_client(settings.jwks_url).get_signing_key_from_jwt, token
            )
            claims = jwt.decode(
                token,
                key.key,
                algorithms=PROVIDER_ALGORITHMS,
                issuer=settings.jwt_issuer,
                audience=settings.jwt_audience,
                options={
                    "require": ["exp", "sub"],
                    "verify_aud": settings.jwt_audience is not None,
                    "verify_iss": settings.jwt_issuer is not None,
                },
            )
        except jwt.PyJWKClientError as exc:
            raise _unauthorized("Unknown signing key") from exc
        except jwt.PyJWTError as exc:
            raise _unauthorized("Invalid or expired token") from exc
        if str(claims["sub"]).startswith(DEMO_SUBJECT_PREFIX):
            raise _unauthorized("Invalid subject")  # provider users can't pose as personas
        is_demo = False
    else:
        raise _unauthorized("Unsupported token algorithm")

    level = claims.get("verification_level")
    return TokenClaims(
        subject=str(claims["sub"]),
        role=claims.get("role") if isinstance(claims.get("role"), str) else None,
        verification_level=level if isinstance(level, int) and 0 <= level <= 3 else None,
        is_demo=is_demo,
    )


# --- FastAPI dependencies ----------------------------------------------------------------


async def get_token_claims(
    settings: Annotated[Settings, Depends(get_settings)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> TokenClaims:
    """Any valid token, even before the person has created a profile."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized("Missing bearer token")
    return await decode_token(credentials.credentials, settings)


@dataclass(frozen=True)
class CurrentUser:
    member_id: uuid.UUID
    role: str
    verification_level: int
    claims: TokenClaims


async def get_current_user(
    request: Request,
    claims: Annotated[TokenClaims, Depends(get_token_claims)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CurrentUser:
    """A signed-in person with a profile. 403 if they still need to create one."""
    row = (
        await session.execute(
            select(Member.id, Member.role, Member.verification_level).where(
                Member.auth_subject == claims.subject
            )
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Create your profile first")
    request.state.user_id = str(row.id)  # picked up by the request log line
    return CurrentUser(row.id, row.role, row.verification_level, claims)


def require_level(level: int):
    """Dependency factory: the caller must have at least this verification level."""

    async def dependency(user: Annotated[CurrentUser, Depends(get_current_user)]) -> CurrentUser:
        if user.verification_level < level:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                detail=f"Verification level {level} required (you have {user.verification_level})",
            )
        return user

    return dependency


def require_admin():
    """Partner admins with a verified role (level 3) run admin actions in the MVP."""

    async def dependency(
        user: Annotated[CurrentUser, Depends(require_level(LEVEL_INTROS))],
    ) -> CurrentUser:
        if user.role != "partner_admin":
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Admins only")
        return user

    return dependency


CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
