"""Claiming a startup (F3): prove you have an email address on its website domain.

1. POST /claim with an email on the domain. We create a 6-digit code and "send" it.
2. POST /claim/verify with the code. If it matches, the startup is yours.

Email sending is simulated in this MVP: outside production (or in a public demo) the
code is returned in the response as `dev_code` so the demo can continue on screen.
Real email delivery can be added behind send_claim_code() later.
"""

import hashlib
import hmac
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from app.config import Settings

CODE_TTL = timedelta(minutes=30)
MAX_ATTEMPTS = 5


def email_domain(email: str) -> str | None:
    local, sep, domain = email.strip().lower().rpartition("@")
    if not sep or not local or "." not in domain:
        return None
    return domain


def domain_matches(email_dom: str, website_domain: str) -> bool:
    """team@terragrid.example and team@mail.terragrid.example both prove terragrid.example."""
    site = website_domain.lower().removeprefix("www.")
    return email_dom == site or email_dom.endswith("." + site)


def new_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_code(claim_id: uuid.UUID, code: str) -> str:
    # The claim id acts as a salt; with only 5 attempts allowed, guessing is hopeless.
    return hashlib.sha256(f"{claim_id}:{code}".encode()).hexdigest()


def code_matches(claim_id: uuid.UUID, code: str, code_hash: str) -> bool:
    return hmac.compare_digest(hash_code(claim_id, code), code_hash)


def expires_at() -> datetime:
    return datetime.now(UTC) + CODE_TTL


def can_show_dev_code(settings: Settings) -> bool:
    return settings.env != "production" or settings.demo_public


class EmailNotConfigured(Exception):
    pass


def send_claim_code(settings: Settings, email: str, startup_name: str, code: str) -> str | None:
    """Deliver the code. Returns the code when we may show it on screen (simulated
    email), else raises until a real email provider is wired in."""
    if can_show_dev_code(settings):
        return code
    raise EmailNotConfigured
