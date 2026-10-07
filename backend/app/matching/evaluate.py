"""How often does the scorer agree with hand-labelled pairs? (tests/eval/pairs.json)

    uv run python -m app.matching.evaluate      # or: make eval

Each pair is scored directly (bypassing candidate generation) and called "good" if its
score reaches the threshold for its kind. We report:
- agreement: share of pairs where the scorer's call equals the label;
- ranking: for members with both good and bad pairs, how often a good pair outscores
  a bad one (independent of any threshold).
Run against a freshly reset demo database.
"""

import asyncio
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db import make_engine
from app.geo import member_center, point
from app.graph import best_trust_path
from app.jobs import job_roles, member_skills, startup_need_caps
from app.matching.scoring import score_pair, student_job_score
from app.matching.service import load_context, weights_from
from app.models import Job, Startup
from app.seed.ids import member_id
from app.skill_match import skill_match

PAIRS_FILE = Path(__file__).resolve().parents[2] / "tests" / "eval" / "pairs.json"


@dataclass
class Result:
    member: str
    candidate: str
    kind: str
    label: str
    score: float
    predicted: str
    why: str

    @property
    def agrees(self) -> bool:
        return self.label == self.predicted


async def _job_score(session, settings: Settings, student_key: str, ref: str) -> float:
    domain, title = ref.split("#", 1)
    sid = member_id(student_key)
    lat, lng = await member_center(session, sid, settings)
    row = (
        await session.execute(
            select(Job.id, Startup.id, func.ST_Distance(Startup.location, point(lat, lng)) / 1000)
            .join(Startup, Startup.id == Job.startup_id)
            .where(Startup.website_domain == domain, Job.title == title)
        )
    ).one_or_none()
    if row is None:
        raise ValueError(f"job not found in the seed: {ref}")
    job_id, startup_id, km = row
    if km > settings.student_radius_km:
        return 0.0  # the distance limit is a hard filter
    role = next(
        r for r in (await job_roles(session, [startup_id]))[startup_id] if r["id"] == job_id
    )
    needs = (await startup_need_caps(session, [startup_id])).get(startup_id, [])
    m = skill_match(await member_skills(session, sid), [role], needs)
    return student_job_score(m.score, km, settings.student_radius_km)


async def evaluate(session, settings: Settings, pairs_file: Path = PAIRS_FILE) -> list[Result]:
    doc = json.loads(pairs_file.read_text())
    thresholds = doc["thresholds"]
    ctx = await load_context(session)
    weights = weights_from(settings)
    results = []
    for p in doc["pairs"]:
        kind = "job" if p["candidate"]["type"] == "job" else "network"
        if kind == "job":
            score = await _job_score(session, settings, p["member"], p["candidate"]["key"])
        else:
            a, b = member_id(p["member"]), member_id(p["candidate"]["key"])
            path = best_trust_path(ctx.adjacency, a, b)
            score, _ = score_pair(ctx.members[a], ctx.members[b], ctx.sims, path, weights)
        predicted = "good" if score >= thresholds[kind] else "bad"
        results.append(
            Result(p["member"], p["candidate"]["key"], kind, p["label"], score, predicted, p["why"])
        )
    return results


def summary(results: list[Result]) -> dict:
    agreement = sum(r.agrees for r in results) / len(results)
    wins = total = 0
    for member in {r.member for r in results}:
        mine = [r for r in results if r.member == member]
        for g in (r for r in mine if r.label == "good"):
            for b in (r for r in mine if r.label == "bad"):
                total += 1
                wins += g.score > b.score
    return {
        "pairs": len(results),
        "agreement": round(agreement, 3),
        "ranking": round(wins / total, 3) if total else None,
        "ranking_comparisons": total,
    }


async def _run(settings: Settings) -> list[Result]:
    engine = make_engine(settings.database_url)
    try:
        async with AsyncSession(engine) as session:
            return await evaluate(session, settings)
    finally:
        await engine.dispose()


def main() -> int:
    results = asyncio.run(_run(get_settings()))
    for r in results:
        mark = "ok  " if r.agrees else "MISS"
        print(f"{mark} {r.label:4} {r.score:5.3f}  {r.member} → {r.candidate}  ({r.why})")
    s = summary(results)
    print(
        f"\n{s['pairs']} pairs · agreement {s['agreement']:.0%} · good-above-bad ranking "
        f"{s['ranking']:.0%} over {s['ranking_comparisons']} comparisons"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
