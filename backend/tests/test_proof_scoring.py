"""The proof-of-work part of a student's score (pure functions)."""

import pytest

from app.matching.scoring import (
    CIRCUIT_WEIGHT,
    FOUNDER_RATING_WEIGHT,
    GITHUB_SIGNAL_CAP,
    PROOF_SHARE,
    StudentProof,
    applicant_rank_score,
    github_signal,
    proof_bonus,
    student_job_score,
)

JOB = ["backend_development", "data_engineering"]
MAX_GITHUB = StudentProof(
    github_caps=frozenset(JOB), github_repos=10, github_active_weeks=12, github_external_prs=50
)


def test_github_signal_is_capped():
    bonus, parts = proof_bonus(MAX_GITHUB, JOB)
    assert parts["github_signal"] == pytest.approx(GITHUB_SIGNAL_CAP)
    assert bonus == pytest.approx(GITHUB_SIGNAL_CAP)


def test_github_never_outweighs_founder_ratings_or_circuits():
    assert GITHUB_SIGNAL_CAP < FOUNDER_RATING_WEIGHT
    assert GITHUB_SIGNAL_CAP < CIRCUIT_WEIGHT
    github, _ = proof_bonus(MAX_GITHUB, JOB)
    rated, _ = proof_bonus(StudentProof(founder_ratings=(4,)), JOB)
    one_circuit, _ = proof_bonus(StudentProof(circuits_completed=1), JOB)
    assert rated > github
    assert one_circuit > github


def test_github_only_counts_for_what_the_job_needs():
    proof = StudentProof(github_caps=frozenset({"frontend_development"}), github_repos=3)
    assert github_signal(proof, JOB) == 0.0
    half = StudentProof(github_caps=frozenset({"backend_development"}), github_repos=3)
    assert github_signal(half, JOB) == pytest.approx(0.5 * 0.5)


def test_non_coders_can_reach_the_same_cap():
    portfolio = StudentProof(portfolio_caps=frozenset({"ui_ux_design"}), portfolio_items=2)
    design_job = ["ui_ux_design"]
    designer, parts = proof_bonus(portfolio, design_job)
    coder, _ = proof_bonus(
        StudentProof(github_caps=frozenset(design_job), github_repos=3, github_active_weeks=1,
                     github_external_prs=2),
        design_job,
    )  # fmt: skip
    assert designer == pytest.approx(coder) == pytest.approx(GITHUB_SIGNAL_CAP)
    assert parts["portfolio_signal"] == pytest.approx(GITHUB_SIGNAL_CAP)


def test_github_and_portfolio_dont_add_up():
    both = StudentProof(
        github_caps=frozenset(JOB), github_repos=3, github_active_weeks=1, github_external_prs=2,
        portfolio_caps=frozenset(JOB), portfolio_items=2,
    )  # fmt: skip
    bonus, _ = proof_bonus(both, JOB)
    assert bonus == pytest.approx(GITHUB_SIGNAL_CAP)


def test_everything_together_fills_the_proof_share():
    full = StudentProof(
        github_caps=frozenset(JOB), github_repos=3, github_active_weeks=1, github_external_prs=2,
        founder_ratings=(5, 5), circuits_completed=2,
    )  # fmt: skip
    bonus, _ = proof_bonus(full, JOB)
    assert bonus == pytest.approx(PROOF_SHARE)
    assert student_job_score(100, 0, 10, bonus) == pytest.approx(1.0)


def test_proof_breaks_ties_but_skills_still_lead():
    no_proof = student_job_score(80, 2, 10, 0.0)
    with_github = student_job_score(80, 2, 10, GITHUB_SIGNAL_CAP)
    better_skills = student_job_score(90, 2, 10, 0.0)
    assert with_github > no_proof
    assert better_skills > with_github  # 10 skill points beat a maxed GitHub


def test_applicant_rank_score():
    assert applicant_rank_score(100, 0.0) == 86
    assert applicant_rank_score(100, PROOF_SHARE) == 100
    assert applicant_rank_score(70, GITHUB_SIGNAL_CAP) > applicant_rank_score(70, 0.0)
