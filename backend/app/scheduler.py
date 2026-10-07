"""Scheduled jobs (APScheduler), started with the API process.

- Every MATCH_REFRESH_HOURS: embed new needs/offers and recompute everyone's matches.
- Every hour: expire intro requests nobody answered within INTRO_EXPIRY_DAYS, and
  circuits nobody fully accepted within CIRCUIT_CONSENT_HOURS.
- Weekly (CIRCUIT_ROUND_DAY at CIRCUIT_ROUND_HOUR, UTC): the exchange circuit round.
Disabled with SCHEDULER_ENABLED=false (tests, or when a separate worker runs it).
"""

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db import get_engine

log = structlog.get_logger("scheduler")


async def refresh_matches(settings: Settings) -> None:
    from app.embeddings import embed_pending, get_embedding_provider
    from app.matching.service import compute_all

    try:
        async with AsyncSession(get_engine()) as session, session.begin():
            await embed_pending(session, get_embedding_provider(settings))
            await compute_all(session, settings)
    except Exception:  # a failed run must not kill the scheduler; the next one retries
        log.exception("refresh_matches_failed")


async def expire_stale(settings: Settings) -> None:
    from app.circuits.service import expire_stale as expire_circuits
    from app.intros import expire_stale as expire_intros

    try:
        async with AsyncSession(get_engine()) as session, session.begin():
            intros = await expire_intros(session, settings.intro_expiry_days)
            circuits = await expire_circuits(session)
        if intros or circuits:
            log.info("expired", intros=intros, circuits=circuits)
    except Exception:
        log.exception("expire_stale_failed")


async def circuit_round(settings: Settings) -> None:
    from app.circuits.service import run_round

    try:
        async with AsyncSession(get_engine()) as session, session.begin():
            result = await run_round(session, settings)
        log.info("circuit_round", round=result.round_key, circuits=len(result.chosen))
    except Exception:
        log.exception("circuit_round_failed")


def start_scheduler(settings: Settings) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(
        refresh_matches,
        "interval",
        hours=settings.match_refresh_hours,
        args=[settings],
        id="refresh_matches",
        max_instances=1,  # never two at once
        coalesce=True,  # if runs were missed (laptop asleep), run once, not many times
    )
    scheduler.add_job(
        expire_stale,
        "interval",
        hours=1,
        args=[settings],
        id="expire_stale",
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        circuit_round,
        "cron",
        day_of_week=settings.circuit_round_day,
        hour=settings.circuit_round_hour,
        args=[settings],
        id="circuit_round",
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    log.info("scheduler_started", match_refresh_hours=settings.match_refresh_hours)
    return scheduler
