"""The people graph behind one interface.

Today Postgres answers graph questions (connections table + recursive SQL). A future
Neo4j implementation only needs to provide the same methods.
"""

import uuid
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import select, text, tuple_
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.matching.scoring import TWO_HOP_DISCOUNT, TrustPath
from app.models import Connection

Adjacency = dict[uuid.UUID, dict[uuid.UUID, float]]  # member -> {neighbour: strength}


@dataclass(frozen=True)
class Tie:
    strength: float
    source: str  # how they know each other, e.g. "mentored", "worked_together"


@dataclass(frozen=True)
class CanHelp:
    """giver has an offer for something receiver needs (exchange circuits, F6)."""

    giver: uuid.UUID
    receiver: uuid.UUID
    capability_id: str
    similarity: float | None  # cosine similarity of the offer and need texts


@dataclass(frozen=True)
class Path:
    members: list[uuid.UUID]  # start ... goal
    weakest: float  # the weakest tie on the path


class GraphStore(Protocol):
    async def adjacency(self, session) -> Adjacency: ...

    async def paths(
        self, session, start: uuid.UUID, goal: uuid.UUID, max_hops: int = 2
    ) -> list[Path]: ...

    async def ties(
        self, session, pairs: list[tuple[uuid.UUID, uuid.UUID]]
    ) -> dict[frozenset[uuid.UUID], Tie]: ...

    async def connect(
        self, session, a: uuid.UUID, b: uuid.UUID, strength: float, source: str
    ) -> None: ...

    async def can_help(self, session, min_level: int) -> list[CanHelp]: ...


class PostgresGraph:
    async def adjacency(self, session) -> Adjacency:
        adj: Adjacency = {}
        rows = await session.execute(text("SELECT member_a, member_b, strength FROM connections"))
        for a, b, s in rows:
            adj.setdefault(a, {})[b] = s
            adj.setdefault(b, {})[a] = s
        return adj

    async def paths(self, session, start, goal, max_hops=2) -> list[Path]:
        """All simple paths of up to max_hops between two members, strongest first,
        found with a recursive SQL query that walks the connections table."""
        rows = await session.execute(
            text(
                """
                WITH RECURSIVE edges AS (
                    SELECT member_a AS src, member_b AS dst, strength FROM connections
                    UNION ALL
                    SELECT member_b, member_a, strength FROM connections
                ), walk AS (
                    SELECT dst AS node, ARRAY[src, dst] AS path, strength AS weakest
                    FROM edges WHERE src = :start
                    UNION ALL
                    SELECT e.dst, w.path || e.dst, LEAST(w.weakest, e.strength)
                    FROM walk w JOIN edges e ON e.src = w.node
                    WHERE array_length(w.path, 1) <= :max_hops AND NOT e.dst = ANY(w.path)
                )
                SELECT path, weakest FROM walk WHERE node = :goal
                ORDER BY array_length(path, 1), weakest DESC
                """
            ),
            {"start": start, "goal": goal, "max_hops": max_hops},
        )
        return [Path(list(p), w) for p, w in rows]

    async def ties(self, session, pairs):
        """The direct tie for each pair (either order), keyed by frozenset({a, b})."""
        if not pairs:
            return {}
        ordered = list({(min(a, b), max(a, b)) for a, b in pairs})
        rows = await session.execute(
            select(Connection.member_a, Connection.member_b, Connection.strength, Connection.source)
            .where(tuple_(Connection.member_a, Connection.member_b).in_(ordered))
        )  # fmt: skip
        return {frozenset((a, b)): Tie(s, src) for a, b, s, src in rows}

    async def connect(self, session, a, b, strength, source):
        """Add a tie unless the two are already connected (keeps the existing one)."""
        await session.execute(
            pg_insert(Connection)
            .values(member_a=min(a, b), member_b=max(a, b), strength=strength, source=source)
            .on_conflict_do_nothing(constraint="uq_connections_pair")
        )

    async def can_help(self, session, min_level):
        """CAN_HELP edges between members who opted in to circuits and have at least
        min_level. A founder's needs include their startup's needs (as in matching)."""
        rows = await session.execute(
            text(
                """
                WITH member_needs AS (
                    SELECT owner_id AS member_id, capability_id, embedding
                    FROM needs WHERE owner_type = 'member' AND active
                    UNION ALL
                    SELECT team.member_id, n.capability_id, n.embedding
                    FROM needs n
                    JOIN (
                        SELECT startup_id, member_id FROM startup_members
                        UNION
                        SELECT id, claimed_by_member_id FROM startups
                        WHERE claimed_by_member_id IS NOT NULL
                    ) team ON team.startup_id = n.owner_id
                    WHERE n.owner_type = 'startup' AND n.active
                ), pool AS (
                    SELECT id FROM members
                    WHERE circuits_opt_in AND verification_level >= :min_level
                )
                SELECT o.member_id, n.member_id, o.capability_id,
                       MAX(1 - (o.embedding <=> n.embedding)) AS similarity
                FROM offers o
                JOIN member_needs n ON n.capability_id = o.capability_id
                WHERE o.active AND o.member_id <> n.member_id
                  AND o.member_id IN (SELECT id FROM pool)
                  AND n.member_id IN (SELECT id FROM pool)
                GROUP BY o.member_id, n.member_id, o.capability_id
                """
            ),
            {"min_level": min_level},
        )
        return [CanHelp(g, r, cap, sim) for g, r, cap, sim in rows]


def best_trust_path(adj: Adjacency, a: uuid.UUID, b: uuid.UUID) -> TrustPath | None:
    """The strongest 1-2 hop path between two members, from an in-memory adjacency
    (used when scoring thousands of pairs at once). Two hops are discounted."""
    direct = adj.get(a, {}).get(b)
    best = TrustPath(direct, 1) if direct else None
    for mutual, s1 in adj.get(a, {}).items():
        s2 = adj.get(mutual, {}).get(b)
        if s2 and mutual != b:
            strength = min(s1, s2) * TWO_HOP_DISCOUNT
            if best is None or strength > best.strength:
                best = TrustPath(strength, 2, mutual)
    return best


def get_graph() -> GraphStore:
    return PostgresGraph()
