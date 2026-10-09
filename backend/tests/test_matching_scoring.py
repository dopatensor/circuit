"""Unit tests for the pure matching functions (no database)."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.matching.ranking import Scored, rank
from app.matching.reasons import job_reason, match_reason
from app.matching.scoring import (
    PROOF_SHARE,
    Components,
    Item,
    Party,
    TrustPath,
    Weights,
    affinity,
    complementarity,
    direction,
    is_bridge,
    item_fit,
    load_penalty,
    score_pair,
    student_job_score,
    timing,
)

NOW = datetime(2026, 10, 7, tzinfo=UTC)
W = Weights()


def item(cap: str, days_old: int = 0) -> Item:
    return Item(uuid.uuid4(), cap, NOW - timedelta(days=days_old))


def party(name="P", sector=None, traits=(), needs=(), offers=(), slots=3, pending=0, kind="member"):
    return Party(
        id=uuid.uuid4(), kind=kind, name=name, sector=sector, traits=frozenset(traits),
        needs=tuple(item(c) if isinstance(c, str) else c for c in needs),
        offers=tuple(item(c) if isinstance(c, str) else c for c in offers),
        open_intro_slots=slots, pending_requests=pending,
    )  # fmt: skip


# --- fits and directions ---------------------------------------------------------------


def test_same_capability_is_a_full_fit():
    assert item_fit(item("marketing"), item("marketing"), {}) == 1.0


def test_different_capability_needs_semantic_similarity():
    need, offer = item("marketing"), item("technical_marketing")
    assert item_fit(need, offer, {}) == 0.0
    assert item_fit(need, offer, {(need.id, offer.id): 0.50}) == 0.0  # unrelated text
    assert item_fit(need, offer, {(need.id, offer.id): 0.85}) == pytest.approx(0.8)
    mid = item_fit(need, offer, {(need.id, offer.id): 0.725})
    assert 0.3 < mid < 0.5


def test_direction_rewards_the_best_fit_most():
    value, met = direction((item("marketing"), item("fundraising")), (item("marketing"),), {})
    assert value == pytest.approx(0.7 * 1.0 + 0.3 * 0.5)
    assert met == ("marketing",)
    assert direction((), (item("marketing"),), {}) == (0.0, ())


def test_complementarity_counts_both_directions():
    one_way = complementarity(party(needs=["marketing"]), party(offers=["marketing"]), {})
    two_way = complementarity(
        party(needs=["marketing"], offers=["hiring"]),
        party(needs=["hiring"], offers=["marketing"]),
        {},
    )
    assert one_way[0] == pytest.approx(0.8)
    assert two_way[0] == pytest.approx(1.0)
    # gets: the candidate helps the member; gives: the member helps the candidate
    member, cand = party(needs=["marketing"]), party(offers=["marketing"])
    _, gets, gives, gets_caps, gives_caps = complementarity(member, cand, {})
    assert (gets, gives, gets_caps, gives_caps) == (1.0, 0.0, ("marketing",), ())
    _, gets, gives, _, gives_caps = complementarity(cand, member, {})
    assert (gets, gives, gives_caps) == (0.0, 1.0, ("marketing",))


def test_affinity_from_shared_traits():
    a = party(traits=["long_sales_cycle", "technical_buyers", "b2b"])
    assert affinity(a, party(traits=["long_sales_cycle", "technical_buyers"])) == (
        pytest.approx(2 / 3), ("long_sales_cycle", "technical_buyers"),
    )  # fmt: skip
    assert affinity(a, a)[0] == 1.0
    assert affinity(a, party())[0] == 0.0


def test_timing_decays_with_need_age():
    assert timing(party(needs=[item("hiring", 3)]), party(), NOW) == 1.0
    assert timing(party(needs=[item("hiring", 120)]), party(), NOW) == 0.3
    assert 0.3 < timing(party(needs=[item("hiring", 50)]), party(), NOW) < 1.0
    assert timing(party(), party(), NOW) == 0.5


def test_load_penalty():
    assert load_penalty(party(slots=4, pending=1)) == 0.25
    assert load_penalty(party(slots=2, pending=5)) == 1.0
    assert load_penalty(party(slots=0)) == 1.0


def test_bridge_needs_different_sectors_and_real_complementarity():
    a, b = party(sector="biotech"), party(sector="deeptech")
    assert is_bridge(a, b, 0.8)
    assert not is_bridge(a, b, 0.2)
    assert not is_bridge(a, party(sector="biotech"), 0.8)
    assert not is_bridge(a, party(sector=None), 0.8)


# --- the full score ---------------------------------------------------------------------


def test_score_formula_matches_the_spec():
    member = party(needs=["marketing"], traits=["b2b"])
    cand = party(offers=["marketing"], traits=["b2b"], slots=4, pending=1)
    score, c = score_pair(member, cand, {}, TrustPath(0.5, 2), W, NOW)
    expected = (
        0.5 * c.complementarity + 0.2 * c.affinity + 0.15 * 0.5 + 0.1 * c.timing - 0.15 * 0.25
    )
    assert score == pytest.approx(expected)
    assert c.as_dict()["gets_caps"] == ["marketing"] and c.hops == 2


def test_complementary_stranger_beats_similar_friend():
    """Our differentiator: what you need and offer matters more than who you know."""
    member = party(sector="biotech", needs=["marketing"], traits=["b2b"])
    helper = party(sector="deeptech", offers=["marketing"])
    friend = party(sector="biotech", offers=["lab_research"], traits=["b2b"])
    s_helper, _ = score_pair(member, helper, {}, None, W, NOW)
    s_friend, _ = score_pair(member, friend, {}, TrustPath(0.9, 1), W, NOW)
    assert s_helper > s_friend


def test_weights_are_configurable():
    member = party(needs=["marketing"])
    cand = party(offers=["marketing"])
    low, _ = score_pair(member, cand, {}, None, Weights(complementarity=0.1), NOW)
    high, _ = score_pair(member, cand, {}, None, Weights(complementarity=0.9), NOW)
    assert high > low


def test_student_job_score():
    # Without proof of work the score tops out below 1; full proof fills the rest.
    assert student_job_score(100, 0, 10) == pytest.approx(1.0 - PROOF_SHARE)
    assert student_job_score(100, 0, 10, PROOF_SHARE) == pytest.approx(1.0)
    assert student_job_score(100, 0, 10, 5.0) == pytest.approx(1.0)  # the bonus is capped
    assert student_job_score(100, 1, 10) > student_job_score(100, 5, 10)
    assert student_job_score(100, 9, 10) > student_job_score(80, 0, 10)  # skills dominate


# --- ranking -----------------------------------------------------------------------------


def s(score, bridge=False, sector="saas", group=None, at_capacity=False):
    cid = uuid.uuid4()
    return Scored(cid, score, bridge, sector, group or cid, at_capacity)


def test_rank_reserves_a_quarter_for_bridges():
    locals_ = [s(0.9 - i * 0.01, sector=f"sector{i}") for i in range(10)]
    bridges = [s(0.3, bridge=True, sector=f"b{i}") for i in range(5)]
    out = rank(locals_ + bridges, n=8, bridge_share=0.25)
    assert len(out) == 8
    assert sum(x.is_bridge for x in out) == 2
    assert [x.score for x in out] == sorted((x.score for x in out), reverse=True)


def test_rank_skips_people_at_capacity_and_dedupes_groups():
    group = uuid.uuid4()
    busy = s(0.99, at_capacity=True)
    startup, founder = s(0.8, group=group), s(0.7, group=group)
    out = rank([busy, startup, founder, s(0.5)], n=5)
    ids = {x.candidate_id for x in out}
    assert busy.candidate_id not in ids
    assert startup.candidate_id in ids and founder.candidate_id not in ids


def test_rank_keeps_sectors_varied_but_fills_the_list():
    same = [s(0.9 - i * 0.01, sector="fintech") for i in range(8)]
    other = [s(0.2, sector="agritech")]
    out = rank(same + other, n=6, max_per_sector=4)
    assert sum(x.sector == "fintech" for x in out) == 5  # relaxed only to fill the list
    assert any(x.sector == "agritech" for x in out)


# --- reasons -----------------------------------------------------------------------------

CAPS = {"marketing": "Marketing", "hiring": "Hiring"}
TRAITS = {"long_sales_cycle": "Long sales cycle", "technical_buyers": "Technical buyers"}


def comps(**kw):
    base = dict(
        complementarity=1, gets=1, gives=0, affinity=0, trust_path=0, timing=1, load_penalty=0
    )
    return Components(**{**base, **kw})


def test_reason_for_the_story1_bridge():
    reason = match_reason(
        "Kavya Menon",
        comps(
            gets_caps=("marketing",),
            shared_traits=("long_sales_cycle", "technical_buyers"),
            hops=2,
        ),
        is_bridge=True, member_sector="biotech", candidate_sector="deeptech",
        cap_names=CAPS, trait_names=TRAITS, via_name="Nandini Rao",
    )  # fmt: skip
    assert reason == (
        "Kavya Menon offers marketing, which you need · both: long sales cycle, technical "
        "buyers · across sectors (deeptech → biotech) · you both know Nandini Rao"
    )


def test_reason_for_a_two_way_trade():
    reason = match_reason(
        "Arjun", comps(gets_caps=("hiring",), gives_caps=("marketing",)), is_bridge=False,
        member_sector=None, candidate_sector=None, cap_names=CAPS, trait_names=TRAITS,
    )  # fmt: skip
    assert reason.startswith("You can trade: Arjun offers hiring, you offer marketing")


def test_job_reason():
    r = job_reason(100, ["marketing"], 1.13, "internship", True, CAPS)
    assert r == "100% skills match (marketing) · 1.1 km away · paid internship"
