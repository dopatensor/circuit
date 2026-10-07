"""Append-only product events (F10).

Payloads must never contain names, emails, phone numbers, free text written by users,
or tokens: record ids, counts and categories only.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Event


async def record_event(
    session: AsyncSession,
    type_: str,
    *,
    actor_id: uuid.UUID | None,
    target_type: str | None = None,
    target_id: uuid.UUID | str | None = None,
    payload: dict | None = None,
) -> None:
    """Add an event to the current transaction (it commits with the action it describes)."""
    session.add(
        Event(
            actor_id=actor_id,
            type=type_,
            target_type=target_type,
            target_id=str(target_id) if target_id is not None else None,
            payload=payload or {},
        )
    )
