"""The match cache behind one interface.

Today the match_results table is the cache (precomputed by the background job). A
future Redis implementation only needs to provide the same methods.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from sqlalchemy import delete, insert, select

from app.models import MatchResult


@dataclass(frozen=True)
class CachedMatch:
    candidate_id: uuid.UUID
    candidate_type: str
    score: float
    components: dict
    reason: str
    is_bridge: bool
    computed_at: datetime | None = None


class MatchCache(Protocol):
    async def get(self, session, member_id: uuid.UUID) -> list[CachedMatch] | None: ...

    async def put(self, session, member_id: uuid.UUID, matches: list[CachedMatch]) -> None: ...


class PostgresMatchCache:
    async def get(self, session, member_id):
        rows = (
            await session.scalars(
                select(MatchResult)
                .where(MatchResult.member_id == member_id)
                .order_by(MatchResult.score.desc(), MatchResult.candidate_id)
            )
        ).all()
        if not rows:
            return None
        return [
            CachedMatch(
                r.candidate_id,
                r.candidate_type,
                r.score,
                r.components,
                r.reason,
                r.is_bridge,
                r.computed_at,
            )  # fmt: skip
            for r in rows
        ]

    async def put(self, session, member_id, matches):
        """Replace this member's results in one go (inside the caller's transaction)."""
        await session.execute(delete(MatchResult).where(MatchResult.member_id == member_id))
        if matches:
            await session.execute(
                insert(MatchResult),
                [
                    {
                        "member_id": member_id,
                        "candidate_id": m.candidate_id,
                        "candidate_type": m.candidate_type,
                        "score": m.score,
                        "components": m.components,
                        "reason": m.reason,
                        "is_bridge": m.is_bridge,
                    }
                    for m in matches
                ],
            )


def get_match_cache() -> MatchCache:
    return PostgresMatchCache()
