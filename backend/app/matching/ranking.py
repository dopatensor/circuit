"""Turn scored candidates into a short, varied list (F4).

1. Capacity: people with no free intro slots are left out.
2. One entry per group (a startup and its own team count as one).
3. ~25% of the list is reserved for bridge (cross-sector) matches, if there are any.
4. Diversity: at most `max_per_sector` results from one sector, relaxed only if the
   list would otherwise be short.
"""

import math
import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class Scored:
    candidate_id: uuid.UUID
    score: float
    is_bridge: bool
    sector: str | None
    group: uuid.UUID  # candidates sharing a group are alternatives (startup + its team)
    at_capacity: bool = False


def rank(
    items: list[Scored], n: int, bridge_share: float = 0.25, max_per_sector: int = 4
) -> list[Scored]:
    available = [s for s in items if not s.at_capacity]
    best_per_group: dict[uuid.UUID, Scored] = {}
    for s in available:
        if s.group not in best_per_group or s.score > best_per_group[s.group].score:
            best_per_group[s.group] = s
    pool = sorted(best_per_group.values(), key=lambda s: (-s.score, str(s.candidate_id)))

    chosen: list[Scored] = []
    quota = math.ceil(n * bridge_share)
    chosen += [s for s in pool if s.is_bridge][:quota]

    def per_sector(sector):
        return sum(1 for c in chosen if c.sector == sector)

    for relaxed in (False, True):
        for s in pool:
            if len(chosen) >= n:
                break
            if s in chosen:
                continue
            if not relaxed and s.sector is not None and per_sector(s.sector) >= max_per_sector:
                continue
            chosen.append(s)
    return sorted(chosen, key=lambda s: (-s.score, str(s.candidate_id)))
