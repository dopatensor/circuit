"""Exchange circuits (F6), the pure part: edges -> 3-person cycles -> chosen circuits.

1. CAN_HELP edges: giver -> receiver when one of the giver's offers meets one of the
   receiver's needs (same capability). Each edge has a weight in 0.4..1.0.
2. Cycles: every 3-person loop A -> B -> C -> A, found with networkx.
3. Score: a loop is only as good as its weakest link, so score = the lowest edge weight.
4. Choice: OR-Tools CP-SAT picks the set of loops with the highest total score in which
   nobody appears twice. (Picking the best loop first and then the next best that
   still fits can do worse; the tests show a case.)

No database here: everything is plain data, so it is fully unit-tested.
"""

import uuid
from dataclasses import dataclass

import networkx as nx
from ortools.sat.python import cp_model

# Edge weight = BASE + FIT * text fit + TRUST * how well they already know each other.
# A capability match alone is worth 0.4; a close wording match and a strong tie add more.
W_BASE, W_FIT, W_TRUST = 0.4, 0.4, 0.2
NO_EMBEDDING_FIT = 0.5  # texts not embedded yet: assume an average fit
MAX_CYCLES = 20_000  # keep the solver fast if the pool grows (best-scoring loops kept)
SOLVER_SECONDS = 10.0


@dataclass(frozen=True)
class Edge:
    giver: uuid.UUID
    receiver: uuid.UUID
    capability_id: str
    weight: float


@dataclass(frozen=True)
class Cycle:
    legs: tuple[Edge, Edge, Edge]  # legs[i].receiver == legs[i + 1].giver

    @property
    def members(self) -> tuple[uuid.UUID, ...]:
        return tuple(leg.giver for leg in self.legs)

    @property
    def score(self) -> float:
        return min(leg.weight for leg in self.legs)  # the weakest link


def edge_weight(similarity: float | None, trust: float) -> float:
    """similarity: cosine similarity of the offer and need texts (None if not embedded);
    trust: 0..1 strength of the best 1-2 hop path between giver and receiver."""
    fit = NO_EMBEDDING_FIT if similarity is None else min(max(similarity, 0.0), 1.0)
    return round(W_BASE + W_FIT * fit + W_TRUST * min(max(trust, 0.0), 1.0), 4)


def best_edges(edges: list[Edge]) -> list[Edge]:
    """One edge per (giver, receiver): the strongest capability between them."""
    best: dict[tuple[uuid.UUID, uuid.UUID], Edge] = {}
    for e in edges:
        key = (e.giver, e.receiver)
        if e.giver == e.receiver:
            continue
        current = best.get(key)
        if current is None or (e.weight, e.capability_id) > (current.weight, current.capability_id):
            best[key] = e
    return list(best.values())


def find_cycles(edges: list[Edge]) -> list[Cycle]:
    """Every directed 3-person loop, each once, rotated to start at its smallest id,
    best score first."""
    graph = nx.DiGraph()
    for e in best_edges(edges):
        graph.add_edge(e.giver, e.receiver, edge=e)
    cycles = []
    for nodes in nx.simple_cycles(graph, length_bound=3):
        if len(nodes) != 3:
            continue
        start = nodes.index(min(nodes, key=str))
        nodes = nodes[start:] + nodes[:start]
        legs = tuple(graph[nodes[i]][nodes[(i + 1) % 3]]["edge"] for i in range(3))
        cycles.append(Cycle(legs))
    cycles.sort(key=lambda c: (-c.score, [str(m) for m in c.members]))
    return cycles[:MAX_CYCLES]


def choose_circuits(cycles: list[Cycle]) -> list[Cycle]:
    """The non-overlapping set of cycles with the highest total score (CP-SAT)."""
    if not cycles:
        return []
    model = cp_model.CpModel()
    picked = [model.new_bool_var(f"c{i}") for i in range(len(cycles))]
    by_member: dict[uuid.UUID, list] = {}
    for var, cycle in zip(picked, cycles, strict=True):
        for m in cycle.members:
            by_member.setdefault(m, []).append(var)
    for variables in by_member.values():
        if len(variables) > 1:
            model.add_at_most_one(variables)
    # CP-SAT works in whole numbers, so scores are scaled to thousandths.
    model.maximize(sum(round(c.score * 1000) * v for c, v in zip(cycles, picked, strict=True)))
    solver = cp_model.CpSolver()
    solver.parameters.num_workers = 1  # one worker + fixed seed = the same answer every run
    solver.parameters.random_seed = 0
    solver.parameters.max_time_in_seconds = SOLVER_SECONDS
    status = solver.solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return []
    chosen = [c for c, v in zip(cycles, picked, strict=True) if solver.value(v)]
    return sorted(chosen, key=lambda c: (-c.score, [str(m) for m in c.members]))
