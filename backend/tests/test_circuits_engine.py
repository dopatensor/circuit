"""Exchange circuit engine (F6) on hand-built graphs where the right answer is known."""

import uuid

import pytest

from app.circuits.engine import (
    NO_EMBEDDING_FIT,
    W_BASE,
    Cycle,
    Edge,
    best_edges,
    choose_circuits,
    edge_weight,
    find_cycles,
)

P = {name: uuid.UUID(int=i + 1) for i, name in enumerate("ABCDEFGHIJ")}


def e(giver: str, receiver: str, weight: float, cap: str = "marketing") -> Edge:
    return Edge(P[giver], P[receiver], cap, weight)


def loop(a: str, b: str, c: str, weight: float) -> list[Edge]:
    return [e(a, b, weight), e(b, c, weight), e(c, a, weight)]


def names(cycle: Cycle) -> str:
    by_id = {v: k for k, v in P.items()}
    return "".join(by_id[m] for m in cycle.members)


def test_edge_weight():
    assert edge_weight(None, 0.0) == pytest.approx(W_BASE + 0.4 * NO_EMBEDDING_FIT)
    assert edge_weight(1.0, 1.0) == 1.0
    assert edge_weight(-0.5, 0.0) == W_BASE  # unrelated wording only drops to the base
    assert edge_weight(0.9, 0.0) < edge_weight(0.9, 0.5)  # knowing each other helps


def test_best_edge_per_pair_and_no_self_loops():
    edges = [e("A", "B", 0.5, "hiring"), e("A", "B", 0.8, "marketing"), e("A", "A", 1.0)]
    (best,) = best_edges(edges)
    assert best.capability_id == "marketing" and best.weight == 0.8


def test_finds_each_triangle_once_scored_by_its_weakest_link():
    edges = [
        e("A", "B", 0.9), e("B", "C", 0.6), e("C", "A", 0.8),  # A -> B -> C -> A
        e("B", "A", 0.7),  # a 2-person swap is not a circuit
        e("C", "D", 0.9), e("D", "E", 0.9), e("E", "C", 0.9),  # C -> D -> E -> C
        e("F", "G", 0.9), e("G", "H", 0.9), e("H", "I", 0.9), e("I", "F", 0.9),  # 4-cycle
        e("A", "C", 0.9),  # wrong direction for a loop through B
    ]  # fmt: skip
    cycles = find_cycles(edges)
    assert [names(c) for c in cycles] == ["CDE", "ABC"]  # best first, each starting at min id
    assert cycles[1].score == 0.6
    abc = cycles[1]
    assert [(leg.giver, leg.receiver) for leg in abc.legs] == [
        (P["A"], P["B"]), (P["B"], P["C"]), (P["C"], P["A"])
    ]  # fmt: skip


def test_solver_beats_greedy_when_the_best_loop_blocks_two_good_ones():
    # ABC is the single best loop, but it shares A with ADE and B with BFG.
    # Greedy takes ABC (0.9) and stops; the best total is ADE + BFG (1.6).
    cycles = find_cycles(
        loop("A", "B", "C", 0.9) + loop("A", "D", "E", 0.8) + loop("B", "F", "G", 0.8)
    )
    assert [names(c) for c in cycles][0] == "ABC"
    chosen = choose_circuits(cycles)
    assert sorted(names(c) for c in chosen) == ["ADE", "BFG"]


def test_chosen_circuits_never_share_a_person():
    edges = (
        loop("A", "B", "C", 0.9) + loop("C", "D", "E", 0.8) + loop("E", "F", "G", 0.85)
        + loop("A", "D", "F", 0.5) + loop("H", "I", "J", 0.4)
    )  # fmt: skip
    chosen = choose_circuits(find_cycles(edges))
    people = [m for c in chosen for m in c.members]
    assert len(people) == len(set(people))
    assert [names(c) for c in chosen] == ["ABC", "EFG", "HIJ"]  # 2.15: the best possible


def test_no_cycles_and_same_answer_every_time():
    assert choose_circuits([]) == []
    assert find_cycles([e("A", "B", 0.9), e("B", "C", 0.9)]) == []
    edges = loop("A", "B", "C", 0.7) + loop("A", "D", "E", 0.7) + loop("B", "D", "F", 0.7)
    first = [names(c) for c in choose_circuits(find_cycles(edges))]
    assert all([names(c) for c in choose_circuits(find_cycles(edges))] == first for _ in range(5))
