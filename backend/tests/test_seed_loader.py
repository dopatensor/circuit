"""Loading the seed into Postgres: idempotent, resettable, and the stories hold in SQL."""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.seed.generator import build_dataset
from app.seed.geo import Point
from app.seed.ids import member_id
from app.seed.loader import load_dataset, truncate_all

pytestmark = pytest.mark.anyio

TABLES = (
    "members", "startups", "startup_members", "capabilities", "traits", "needs", "offers",
    "member_traits", "startup_traits", "member_skills", "connections", "intro_requests",
    "events",
)  # fmt: skip


@pytest.fixture(scope="module")
def dataset():
    return build_dataset(Point(12.9716, 77.5946), "Bengaluru")


async def counts(session) -> dict[str, int]:
    return {t: await session.scalar(text(f"SELECT count(*) FROM {t}")) for t in TABLES}


async def reset(session, dataset) -> None:
    await truncate_all(session)
    await load_dataset(session, dataset)
    await session.commit()


async def test_load_matches_dataset(session, dataset):
    await reset(session, dataset)
    c = await counts(session)
    assert c["members"] == len(dataset.members)
    assert c["startups"] == len(dataset.startups)
    assert c["connections"] == len(dataset.connections)
    assert c["events"] == len(dataset.events)
    member_needs = sum(len(m.needs) for m in dataset.members)
    assert c["needs"] == member_needs + sum(len(s.needs) for s in dataset.startups)


async def test_seed_is_idempotent(session, dataset):
    await reset(session, dataset)
    before = await counts(session)
    await load_dataset(session, dataset)
    await session.commit()
    assert await counts(session) == before


async def test_reseed_keeps_live_claims_and_counters_but_reset_restores(session, dataset):
    await reset(session, dataset)
    rohan = member_id("rohan")
    await session.execute(
        text(
            "UPDATE startups SET claimed_by_member_id = :m, view_count = 999 "
            "WHERE website_domain = 'terragrid.example'"
        ),
        {"m": rohan},
    )
    await session.commit()

    await load_dataset(session, dataset)
    await session.commit()
    row = (
        await session.execute(
            text(
                "SELECT claimed_by_member_id, view_count FROM startups "
                "WHERE website_domain = 'terragrid.example'"
            )
        )
    ).one()
    assert row == (rohan, 999)

    await reset(session, dataset)
    row = (
        await session.execute(
            text(
                "SELECT claimed_by_member_id, view_count FROM startups "
                "WHERE website_domain = 'terragrid.example'"
            )
        )
    ).one()
    assert row == (None, 63)


async def test_events_are_append_only(session, dataset):
    await reset(session, dataset)
    for sql in ("UPDATE events SET type = 'x'", "DELETE FROM events"):
        with pytest.raises(DBAPIError, match="append-only"):
            await session.execute(text(sql))
        await session.rollback()


async def test_student_is_within_3km_of_hiring_startup_in_postgis(session, dataset):
    await reset(session, dataset)
    metres = await session.scalar(
        text(
            "SELECT ST_Distance(m.location, s.location) FROM members m, startups s "
            "WHERE m.id = :ravi AND s.website_domain = 'ledgerloop.example'"
        ),
        {"ravi": member_id("ravi")},
    )
    assert metres < 3000


async def test_two_hop_warm_path_found_with_recursive_sql(session, dataset):
    await reset(session, dataset)
    # The kind of query Phase 5 will use: walk connections up to 2 hops.
    paths = (
        await session.execute(
            text(
                """
                WITH RECURSIVE edges AS (
                    SELECT member_a AS src, member_b AS dst, strength FROM connections
                    UNION ALL
                    SELECT member_b, member_a, strength FROM connections
                ), walk AS (
                    SELECT dst AS node, ARRAY[src, dst] AS path, strength AS weakest
                    FROM edges WHERE src = :start
                    UNION ALL
                    SELECT e.dst, w.path || e.dst, LEAST(w.weakest, e.strength)
                    FROM walk w JOIN edges e ON e.src = w.node
                    WHERE array_length(w.path, 1) < 3 AND NOT e.dst = ANY(w.path)
                )
                SELECT path, weakest FROM walk WHERE node = :goal ORDER BY weakest DESC
                """
            ),
            {"start": member_id("rohan"), "goal": member_id("vikram")},
        )
    ).all()
    assert paths, "Rohan should reach Vikram in 2 hops"
    best_path, weakest = paths[0]
    assert best_path[1] == member_id("lakshmi")
    assert weakest >= 0.8
