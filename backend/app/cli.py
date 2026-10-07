"""Command-line tasks. Run from backend/:

uv run python -m app.cli migrate      # apply database migrations
uv run python -m app.cli seed         # add/refresh seed data, keep live activity
uv run python -m app.cli reset-demo   # wipe everything and restore the demo seed
uv run python -m app.cli dump-seed    # print the generated startups as crawler JSON
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
    finally:
        await engine.dispose()


def _refuse_in_production(settings: Settings, action: str) -> None:
    if settings.env == "production" and not settings.demo_public:
        sys.exit(f"Refusing to {action} with ENV=production (set DEMO_PUBLIC=true for demos).")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    parser.add_argument("command", choices=["migrate", "seed", "reset-demo", "dump-seed"])
    args = parser.parse_args(argv)
    settings = get_settings()

    if args.command == "dump-seed":
        records = [s.record.model_dump() for s in dataset_for(settings).startups]
        json.dump(records, sys.stdout, indent=2, ensure_ascii=False)
        print()
        return

    migrate(settings.database_url)
    if args.command == "migrate":
        return
    _refuse_in_production(settings, args.command)
    asyncio.run(seed(settings.database_url, settings, reset=args.command == "reset-demo"))
    print(f"{args.command}: done")


if __name__ == "__main__":
    main()
