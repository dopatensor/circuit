"""Pure scoring functions for matching (F4). No database, fully unit-tested.

    score = w1*complementarity + w2*affinity + w3*trust_path + w4*timing - w5*load_penalty

- complementarity: how well one side's offers meet the other's needs, in BOTH
  directions. Same capability = a full fit; a different capability whose wording is
  semantically close (embedding similarity) = a partial fit.
- affinity: shared traits (e.g. both sell with a long sales cycle to technical buyers).
- trust_path: strength of the best 1-2 hop connection between the two.
- timing: fresher needs are more urgent.
- load_penalty: people already busy with intro requests are pushed down.

A match across different sectors with real complementarity is a "bridge" match.
"""

import uuid
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal

# Semantic fit: cosine similarity between need and offer embeddings, rescaled so that
# unrelated text (~0.55 for this model) counts 0 and very close text counts up to 0.8.
SEM_FLOOR = 0.60
SEM_CEIL = 0.85
SEM_MAX = 0.8
# Within one direction: the single best fit matters most, breadth adds a little.
BEST_SHARE = 0.7
# Across directions: one-way help is a good match; two-way help is better.
MAIN_DIRECTION_SHARE = 0.8
TRAITS_FOR_FULL_AFFINITY = 3
TWO_HOP_DISCOUNT = 0.8
BRIDGE_MIN_COMPLEMENTARITY = 0.5
FIT_COUNTS_AS_MATCH = 0.5


@dataclass(frozen=True)
class Item:
    """A need or an offer."""

    id: uuid.UUID
    capability_id: str
    created_at: datetime | None = None


@dataclass(frozen=True)
class Party:
    """A member or a startup, as matching sees it."""

    id: uuid.UUID
    kind: Literal["member", "startup"]
    name: str
    sector: str | None
    traits: frozenset[str] = frozenset()
    needs: tuple[Item, ...] = ()
    offers: tuple[Item, ...] = ()
    open_intro_slots: int = 3
    pending_requests: int = 0


@dataclass(frozen=True)
class TrustPath:
    strength: float  # 0..1, already discounted for hops
    hops: int  # 1 = direct, 2 = through one mutual connection
    via: uuid.UUID | None = None


@dataclass(frozen=True)
class Weights:
    complementarity: float = 0.50
    affinity: float = 0.20
    trust_path: float = 0.15
    timing: float = 0.10
    load_penalty: float = 0.15


@dataclass(frozen=True)
class Components:
    complementarity: float
    gets: float  # how well the candidate helps the member
    gives: float  # how well the member helps the candidate
    affinity: float
    trust_path: float
    timing: float
    load_penalty: float
    gets_caps: tuple[str, ...] = ()  # member's needs the candidate can meet
    gives_caps: tuple[str, ...] = ()  # candidate's needs the member can meet
    shared_traits: tuple[str, ...] = ()
    hops: int | None = None
    via: uuid.UUID | None = None
    extra: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "complementarity": round(self.complementarity, 3),
            "gets": round(self.gets, 3),
            "gives": round(self.gives, 3),
            "affinity": round(self.affinity, 3),
            "trust_path": round(self.trust_path, 3),
            "timing": round(self.timing, 3),
            "load_penalty": round(self.load_penalty, 3),
            "gets_caps": list(self.gets_caps),
            "gives_caps": list(self.gives_caps),
            "shared_traits": list(self.shared_traits),
            "hops": self.hops,
            "via": str(self.via) if self.via else None,
            **self.extra,
        }


Sims = Mapping[tuple[uuid.UUID, uuid.UUID], float]  # (need id, offer id) -> cosine


def item_fit(need: Item, offer: Item, sims: Sims) -> float:
    if need.capability_id == offer.capability_id:
        return 1.0
    cosine = sims.get((need.id, offer.id))
    if cosine is None:
        return 0.0
    scaled = (cosine - SEM_FLOOR) / (SEM_CEIL - SEM_FLOOR)
    return max(0.0, min(1.0, scaled)) * SEM_MAX


def direction(needs: tuple[Item, ...], offers: tuple[Item, ...], sims: Sims):
    """How well `offers` meet `needs`. Returns (value 0..1, capabilities met)."""
    if not needs or not offers:
        return 0.0, ()
    best = [max(item_fit(n, o, sims) for o in offers) for n in needs]
    value = BEST_SHARE * max(best) + (1 - BEST_SHARE) * (sum(best) / len(best))
    met = tuple(
        dict.fromkeys(
            n.capability_id for n, b in zip(needs, best, strict=True) if b >= FIT_COUNTS_AS_MATCH
        )
    )
    return value, met


def complementarity(member: Party, candidate: Party, sims: Sims):
    gets, gets_caps = direction(member.needs, candidate.offers, sims)
    gives, gives_caps = direction(candidate.needs, member.offers, sims)
    value = MAIN_DIRECTION_SHARE * max(gets, gives) + (1 - MAIN_DIRECTION_SHARE) * min(gets, gives)
    return value, gets, gives, gets_caps, gives_caps


def affinity(a: Party, b: Party) -> tuple[float, tuple[str, ...]]:
    shared = tuple(sorted(a.traits & b.traits))
    return min(1.0, len(shared) / TRAITS_FOR_FULL_AFFINITY), shared


def trust(path: TrustPath | None) -> float:
    return path.strength if path else 0.0


def timing(member: Party, candidate: Party, now: datetime) -> float:
    """1.0 for needs posted in the last 14 days, falling to 0.3 at 90 days."""
    dates = [n.created_at for n in (*member.needs, *candidate.needs) if n.created_at]
    if not dates:
        return 0.5
    age_days = (now - max(dates)).total_seconds() / 86400
    if age_days <= 14:
        return 1.0
    if age_days >= 90:
        return 0.3
    return 1.0 - 0.7 * (age_days - 14) / 76


def load_penalty(candidate: Party) -> float:
    if candidate.open_intro_slots <= 0:
        return 1.0
    return min(1.0, candidate.pending_requests / candidate.open_intro_slots)


def is_bridge(member: Party, candidate: Party, comp: float) -> bool:
    return (
        member.sector is not None
        and candidate.sector is not None
        and member.sector != candidate.sector
        and comp >= BRIDGE_MIN_COMPLEMENTARITY
    )


def score_pair(
    member: Party,
    candidate: Party,
    sims: Sims,
    path: TrustPath | None,
    weights: Weights,
    now: datetime | None = None,
) -> tuple[float, Components]:
    now = now or datetime.now(UTC)
    comp, gets, gives, gets_caps, gives_caps = complementarity(member, candidate, sims)
    aff, shared = affinity(member, candidate)
    c = Components(
        complementarity=comp,
        gets=gets,
        gives=gives,
        affinity=aff,
        trust_path=trust(path),
        timing=timing(member, candidate, now),
        load_penalty=load_penalty(candidate),
        gets_caps=gets_caps,
        gives_caps=gives_caps,
        shared_traits=shared,
        hops=path.hops if path else None,
        via=path.via if path else None,
    )
    score = (
        weights.complementarity * c.complementarity
        + weights.affinity * c.affinity
        + weights.trust_path * c.trust_path
        + weights.timing * c.timing
        - weights.load_penalty * c.load_penalty
    )
    return score, c


# --- students and jobs ---------------------------------------------------------------------

STUDENT_SKILL_SHARE = 0.85

# Proof of work (R2). On top of the skill match, a student's score gets a small bonus
# for evidence that they can do the work. The weights are ordered on purpose: GitHub
# (or equivalent non-code proof) is capped below both founder ratings and completed
# Circuit projects, so a GitHub profile can never outweigh either of them.
FOUNDER_RATING_WEIGHT = 0.06  # average rating from founders the student helped
CIRCUIT_WEIGHT = 0.05  # completed Circuit projects
GITHUB_SIGNAL_CAP = 0.03  # GitHub, or a portfolio for non-coders: the same cap
PROOF_SHARE = FOUNDER_RATING_WEIGHT + CIRCUIT_WEIGHT + GITHUB_SIGNAL_CAP  # 0.14
FIRST_CIRCUIT_SHARE = 0.7  # one completed circuit counts 70%, two or more 100%
GITHUB_REPOS_FOR_FULL = 3
GITHUB_PRS_FOR_FULL = 2
PORTFOLIO_ITEMS_FOR_FULL = 2


@dataclass(frozen=True)
class StudentProof:
    """Everything about a student's proof of work that scoring uses.

    github_caps / portfolio_caps: capabilities shown by GitHub (verified) and by
    non-code proof items (added by the student). Stars and followers are not here on
    purpose."""

    github_caps: frozenset[str] = frozenset()
    github_repos: int = 0  # original repos with enough of their own commits
    github_active_weeks: int = 0  # in the last 90 days
    github_external_prs: int = 0  # merged, to repos they don't own
    portfolio_caps: frozenset[str] = frozenset()
    portfolio_items: int = 0
    founder_ratings: tuple[int, ...] = ()  # 1..5 each
    circuits_completed: int = 0


def github_strength(repos: int, active_weeks: int, external_prs: int) -> float:
    """0..1: original repos with real commits (half), recent activity (a quarter),
    merged pull requests to other people's repos (a quarter)."""
    return (
        0.5 * min(1.0, repos / GITHUB_REPOS_FOR_FULL)
        + 0.25 * (1.0 if active_weeks > 0 else 0.0)
        + 0.25 * min(1.0, external_prs / GITHUB_PRS_FOR_FULL)
    )


def _relevance(required: Iterable[str], shown: frozenset[str]) -> float:
    required = set(required)
    if not required:
        return 0.0
    return len(required & shown) / len(required)


def github_signal(proof: StudentProof, required: Iterable[str]) -> float:
    """0..1: how much of what the job needs GitHub shows, times how strong the
    GitHub evidence is."""
    strength = github_strength(
        proof.github_repos, proof.github_active_weeks, proof.github_external_prs
    )
    return _relevance(required, proof.github_caps) * strength


def portfolio_signal(proof: StudentProof, required: Iterable[str]) -> float:
    """The same idea for portfolios, Behance/Dribbble links and case studies, so
    students who don't write code aren't at a disadvantage."""
    strength = min(1.0, proof.portfolio_items / PORTFOLIO_ITEMS_FOR_FULL)
    return _relevance(required, proof.portfolio_caps) * strength


def founder_rating_signal(ratings: tuple[int, ...]) -> float:
    return sum(ratings) / (5 * len(ratings)) if ratings else 0.0


def circuit_signal(completed: int) -> float:
    if completed <= 0:
        return 0.0
    return min(1.0, FIRST_CIRCUIT_SHARE + (1 - FIRST_CIRCUIT_SHARE) * (completed - 1))


def proof_bonus(proof: StudentProof, required: Iterable[str]) -> tuple[float, dict]:
    """The proof-of-work part of a student's score (0..PROOF_SHARE) and its parts."""
    required = list(required)
    gh = github_signal(proof, required)
    pf = portfolio_signal(proof, required)
    work = GITHUB_SIGNAL_CAP * max(gh, pf)
    founder = FOUNDER_RATING_WEIGHT * founder_rating_signal(proof.founder_ratings)
    circuits = CIRCUIT_WEIGHT * circuit_signal(proof.circuits_completed)
    parts = {
        "github_signal": round(GITHUB_SIGNAL_CAP * gh, 4),
        "portfolio_signal": round(GITHUB_SIGNAL_CAP * pf, 4),
        "work_proof": round(work, 4),
        "founder_ratings": round(founder, 4),
        "circuits": round(circuits, 4),
    }
    return work + founder + circuits, parts


def student_job_score(
    skill_score: int, distance_km: float, radius_km: float, bonus: float = 0.0
) -> float:
    """Students: the same skill match as the map and job pages (0-100), plus a little
    for being closer, plus the proof-of-work bonus (see proof_bonus). Jobs beyond the
    radius never get here (hard filter). The result stays within 0..1."""
    proximity = max(0.0, 1.0 - distance_km / radius_km) if radius_km > 0 else 0.0
    base = STUDENT_SKILL_SHARE * (skill_score / 100) + (1 - STUDENT_SKILL_SHARE) * proximity
    return (1 - PROOF_SHARE) * base + min(bonus, PROOF_SHARE)


def applicant_rank_score(skill_score: int, bonus: float) -> int:
    """0..100, how founders' applicant lists are ordered: the skill match, plus proof."""
    return round(100 * ((1 - PROOF_SHARE) * skill_score / 100 + min(bonus, PROOF_SHARE)))
