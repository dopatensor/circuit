"""Command-line tasks. Run from backend/:

uv run python -m app.cli migrate      # apply database migrations
uv run python -m app.cli seed         # add/refresh seed data, keep live activity
uv run python -m app.cli reset-demo   # wipe everything and restore the demo seed
uv run python -m app.cli dump-seed    # print the generated startups as crawler JSON
uv run python -m app.cli openapi      # print the API's OpenAPI spec (for the frontend client)
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db import make_engine
from app.seed.generator import build_dataset
from app.seed.geo import Point
from app.seed.loader import load_dataset, truncate_all

ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"


def migrate(database_url: str) -> None:
    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(cfg, "head")


def dataset_for(settings: Settings):
    center = Point(settings.city_center_lat, settings.city_center_lng)
    return build_dataset(center, settings.city_name)


async def seed(database_url: str, settings: Settings, reset: bool) -> None:
    engine = make_engine(database_url)
    try:
        # One transaction: if anything fails, the database is left untouched.
        async with AsyncSession(engine) as session, session.begin():
            if reset:
                await truncate_all(session)
            await load_dataset(session, dataset_for(settings))
            await session.flush()
            await prepare_matches(session, settings)
    finally:
        await engine.dispose()


async def prepare_matches(session, settings: Settings) -> None:
    """Embed new needs/offers, then precompute everyone's matches."""
    from app.embeddings import embed_pending, get_embedding_provider
    from app.matching.service import compute_all

    count = await embed_pending(session, get_embedding_provider(settings))
    result = await compute_all(session, settings)
    print(f"embedded {count} texts; {result['results']} matches for {result['members']} members")


async def compute_matches(database_url: str, settings: Settings) -> None:
    engine = make_engine(database_url)
    try:
        async with AsyncSession(engine) as session, session.begin():
            await prepare_matches(session, settings)
    finally:
        await engine.dispose()


def openapi_json() -> str:
    """The OpenAPI spec as stable JSON. The frontend generates its typed client from it
    (frontend/openapi.json -> src/api/schema.d.ts); a test checks the copy is current."""
    from app.main import create_app

    return json.dumps(create_app().openapi(), indent=2, sort_keys=True, ensure_ascii=False)


def _refuse_in_production(settings: Settings, action: str) -> None:
    if settings.env == "production" and not settings.demo_public:
        sys.exit(f"Refusing to {action} with ENV=production (set DEMO_PUBLIC=true for demos).")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    parser.add_argument(
        "command",
        choices=["migrate", "seed", "reset-demo", "dump-seed", "compute-matches", "openapi"],
    )
    args = parser.parse_args(argv)
    settings = get_settings()

    if args.command == "openapi":
        print(openapi_json())
        return
    if args.command == "dump-seed":
        records = [s.record.model_dump() for s in dataset_for(settings).startups]
        json.dump(records, sys.stdout, indent=2, ensure_ascii=False)
        print()
        return

    migrate(settings.database_url)
    if args.command == "migrate":
        return
    if args.command == "compute-matches":
        asyncio.run(compute_matches(settings.database_url, settings))
        return
    _refuse_in_production(settings, args.command)
    asyncio.run(seed(settings.database_url, settings, reset=args.command == "reset-demo"))
    print(f"{args.command}: done")


if __name__ == "__main__":
    main()
