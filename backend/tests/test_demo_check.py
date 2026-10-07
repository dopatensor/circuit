"""`make demo-check` must pass on a freshly seeded database."""

import pytest

from app.demo_check import STORIES, run_checks
from tests.conftest import make_test_settings

pytestmark = pytest.mark.anyio


async def test_all_demo_stories_pass_on_the_seed(seeded):
    results = await run_checks(make_test_settings())
    failures = [(name, detail) for name, ok, detail in results if not ok]
    assert not failures, failures
    assert len(results) == len(STORIES) == 5


async def test_a_broken_story_is_reported_as_fail(seeded, session):
    from sqlalchemy import text

    await session.execute(
        text("UPDATE members SET circuits_opt_in = false WHERE display_name = 'Priya Sharma'")
    )
    await session.commit()
    try:
        results = {name: ok for name, ok, _ in await run_checks(make_test_settings())}
        assert results["2 Exchange circuit (Asha, Priya, Arjun)"] is False
        assert sum(results.values()) == 4
    finally:
        await session.execute(
            text("UPDATE members SET circuits_opt_in = true WHERE display_name = 'Priya Sharma'")
        )
        await session.commit()
