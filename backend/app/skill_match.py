"""How well a student's skills fit a startup ("match to my skills", F2).

Pure functions, no database: easy to test and to explain in a demo.

Only skills count. The inputs deliberately do not include the student's college, so
the score cannot favour a famous college name.

Score (0-100):
- For each open role, how much of the role's required capabilities the student
  covers, weighted by skill level (strong 1.0, solid 0.8, basic 0.5). A skill below
  the role's minimum level counts at 60%.
- The best-fitting role counts for 80%; covering the startup's other needs adds up
  to 20%. Startups with no open roles are scored on their needs alone.
"""

from dataclasses import dataclass, field

LEVEL_WEIGHT = {1: 0.5, 2: 0.8, 3: 1.0}
BELOW_MIN_FACTOR = 0.6
ROLE_WEIGHT = 0.8
NEEDS_WEIGHT = 0.2


@dataclass(frozen=True)
class RoleFit:
    title: str
    score: float  # 0..1
    matched: list[str]
    missing: list[str]


@dataclass(frozen=True)
class SkillMatch:
    score: int  # 0..100
    best_role: RoleFit | None
    matched: list[str] = field(default_factory=list)  # capabilities the student brings
    missing: list[str] = field(default_factory=list)  # what the best role still needs


def _weight(level: int, min_level: int) -> float:
    w = LEVEL_WEIGHT.get(level, 0.0)
    return w if level >= min_level else w * BELOW_MIN_FACTOR


def _coverage(
    skills: dict[str, int], required: list[str], min_levels: dict[str, int] | None = None
) -> float:
    if not required:
        return 0.0
    mins = min_levels or {}
    return sum(_weight(skills.get(c, 0), mins.get(c, 1)) for c in required) / len(required)


def role_fit(
    skills: dict[str, int],
    title: str,
    required: list[str],
    min_levels: dict[str, int] | None = None,
) -> RoleFit:
    required = list(dict.fromkeys(required))
    return RoleFit(
        title=title,
        score=_coverage(skills, required, min_levels),
        matched=[c for c in required if c in skills],
        missing=[c for c in required if c not in skills],
    )


def skill_match(
    skills: dict[str, int], open_roles: list[dict], need_capabilities: list[str]
) -> SkillMatch:
    """skills: {capability_id: level 1..3}; open_roles (or jobs):
    [{"title", "capabilities": [ids], "min_levels": {id: 1..3} (optional)}]."""
    fits = [
        role_fit(skills, r.get("title", ""), r.get("capabilities", []), r.get("min_levels"))
        for r in open_roles
        if r.get("capabilities")
    ]
    best = max(fits, key=lambda f: (f.score, -len(f.missing)), default=None)
    needs = list(dict.fromkeys(need_capabilities))
    needs_cov = _coverage(skills, needs)

    if best is None:
        raw = needs_cov
    elif not needs:
        raw = best.score
    else:
        raw = ROLE_WEIGHT * best.score + NEEDS_WEIGHT * needs_cov

    matched = list(
        dict.fromkeys((best.matched if best else []) + [c for c in needs if c in skills])
    )
    return SkillMatch(
        score=round(raw * 100),
        best_role=best,
        matched=matched,
        missing=best.missing if best else [c for c in needs if c not in skills],
    )
