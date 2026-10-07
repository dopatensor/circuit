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
from collections.abc import Mapping
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


def student_job_score(skill_score: int, distance_km: float, radius_km: float) -> float:
    """Students: the same skill match as the map and job pages (0-100), plus a little
    for being closer. Jobs beyond the radius never get here (hard filter)."""
    proximity = max(0.0, 1.0 - distance_km / radius_km) if radius_km > 0 else 0.0
    return STUDENT_SKILL_SHARE * (skill_score / 100) + (1 - STUDENT_SKILL_SHARE) * proximity
