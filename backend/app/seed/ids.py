"""Deterministic ids for seeded rows, so the demo is identical after every reset."""

import uuid

_NAMESPACE = uuid.UUID("6f1c2a52-3b0e-4d5f-9c1e-2b7a0c3d9e41")


def seed_uuid(kind: str, key: str) -> uuid.UUID:
    """Same (kind, key) always gives the same UUID, e.g. seed_uuid("member", "asha")."""
    return uuid.uuid5(_NAMESPACE, f"{kind}:{key}")


def member_id(key: str) -> uuid.UUID:
    return seed_uuid("member", key)


def startup_id(domain: str) -> uuid.UUID:
    return seed_uuid("startup", domain)
