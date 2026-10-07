"""Exchange circuit rounds (F6), the database part.

A round: build CAN_HELP edges from the database, leave out people already in an open
circuit, find and choose loops (app.circuits.engine), and store each chosen loop as a
`proposed` circuit with three legs. Each giver accepts or declines their leg within
CIRCUIT_CONSENT_HOURS (72). All three accept -> `active`; anyone declines -> `declined`;
time runs out -> `expired`. Once active, each receiver marks the help they got as done
and rates it; when all three legs are done the circuit is `completed`.
"""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select, update

from app.auth import LEVEL_MATCHES
from app.circuits.engine import Cycle, Edge, choose_circuits, edge_weight, find_cycles
from app.config import Settings
from app.events import record_event
from app.graph import best_trust_path, get_graph
from app.models import Circuit, CircuitLeg

# Don't propose the same three people again soon after they said no (or let it lapse).
REPROPOSE_AFTER = timedelta(days=28)


def round_key(now: datetime) -> str:
    year, week, _ = now.isocalendar()
    return f"{year}-W{week:02d}"


@dataclass
class RoundResult:
    round_key: str
    pool: int  # members with at least one CAN_HELP edge
    edges: int
    cycles_found: int
    chosen: list[Cycle]
    circuit_ids: list[uuid.UUID] = field(default_factory=list)


async def busy_members(session, now: datetime) -> set[uuid.UUID]:
    """People already in an active circuit or one still waiting for answers."""
    open_circuit = or_(
        Circuit.status == "active",
        (Circuit.status == "proposed") & (Circuit.expires_at > now),
    )
    rows = await session.scalars(
        select(CircuitLeg.giver_id).join(Circuit, Circuit.id == CircuitLeg.circuit_id)
        .where(open_circuit)
    )  # fmt: skip
    return set(rows.all())


async def recently_turned_down(session, now: datetime) -> set[frozenset[uuid.UUID]]:
    rows = await session.execute(
        select(CircuitLeg.circuit_id, CircuitLeg.giver_id)
        .join(Circuit, Circuit.id == CircuitLeg.circuit_id)
        .where(
            Circuit.status.in_(("declined", "expired")),
            Circuit.created_at > now - REPROPOSE_AFTER,
        )
    )
    groups: dict[uuid.UUID, set[uuid.UUID]] = {}
    for circuit_id, giver in rows:
        groups.setdefault(circuit_id, set()).add(giver)
    return {frozenset(g) for g in groups.values()}


async def build_edges(session, now: datetime) -> list[Edge]:
    graph = get_graph()
    busy = await busy_members(session, now)
    adjacency = await graph.adjacency(session)
    edges = []
    for row in await graph.can_help(session, min_level=LEVEL_MATCHES):
        if row.giver in busy or row.receiver in busy:
            continue
        trust = best_trust_path(adjacency, row.giver, row.receiver)
        weight = edge_weight(row.similarity, trust.strength if trust else 0.0)
        edges.append(Edge(row.giver, row.receiver, row.capability_id, weight))
    return edges


async def run_round(
    session,
    settings: Settings,
    *,
    actor_id: uuid.UUID | None = None,
    dry_run: bool = False,
    now: datetime | None = None,
) -> RoundResult:
    """Run one circuit round. dry_run=True finds and chooses loops but saves nothing
    (used by demo-check and the admin preview)."""
    now = now or datetime.now(UTC)
    if not dry_run:
        await expire_stale(session, now)
    edges = await build_edges(session, now)
    turned_down = await recently_turned_down(session, now)
    cycles = [c for c in find_cycles(edges) if frozenset(c.members) not in turned_down]
    chosen = choose_circuits(cycles)
    result = RoundResult(
        round_key=round_key(now),
        pool=len({e.giver for e in edges} | {e.receiver for e in edges}),
        edges=len(edges),
        cycles_found=len(cycles),
        chosen=chosen,
    )
    if not dry_run:
        expires = now + timedelta(hours=settings.circuit_consent_hours)
        for cycle in chosen:
            circuit = Circuit(
                round_key=result.round_key, status="proposed", score=cycle.score,
                created_at=now, expires_at=expires,
            )  # fmt: skip
            session.add(circuit)
            await session.flush()
            for position, leg in enumerate(cycle.legs):
                session.add(
                    CircuitLeg(
                        circuit_id=circuit.id, position=position, giver_id=leg.giver,
                        receiver_id=leg.receiver, capability_id=leg.capability_id,
                    )
                )  # fmt: skip
            result.circuit_ids.append(circuit.id)
            await record_event(
                session, "circuit.proposed", actor_id=None, target_type="circuit",
                target_id=circuit.id, payload={"score": round(cycle.score, 3)},
            )  # fmt: skip
    await record_event(
        session, "circuits.round_run", actor_id=actor_id,
        payload={"dry_run": dry_run, "pool": result.pool, "edges": result.edges,
                 "cycles": result.cycles_found, "chosen": len(chosen)},
    )  # fmt: skip
    return result


async def expire_stale(session, now: datetime | None = None) -> int:
    """Proposed circuits whose 72 hours ran out become expired (hourly job, and the
    start of every round)."""
    now = now or datetime.now(UTC)
    ids = (
        await session.scalars(
            update(Circuit)
            .where(Circuit.status == "proposed", Circuit.expires_at <= now)
            .values(status="expired")
            .returning(Circuit.id)
        )
    ).all()
    for circuit_id in ids:
        await record_event(
            session, "circuit.expired", actor_id=None, target_type="circuit", target_id=circuit_id
        )
    return len(ids)
