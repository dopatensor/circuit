import pytest
from sqlalchemy import text

from app.scheduler import refresh_matches, start_scheduler
from tests.conftest import make_test_settings

pytestmark = pytest.mark.anyio


async def test_scheduler_registers_the_matching_job():
    scheduler = start_scheduler(make_test_settings(match_refresh_hours=6))
    try:
        (job,) = scheduler.get_jobs()
        assert job.id == "refresh_matches" and job.trigger.interval.total_seconds() == 6 * 3600
    finally:
        scheduler.shutdown(wait=False)


async def test_refresh_job_recomputes_matches(session, seeded):
    await session.execute(text("DELETE FROM match_results"))
    await session.commit()
    await refresh_matches(make_test_settings())
    assert await session.scalar(text("SELECT count(*) FROM match_results")) > 1000
