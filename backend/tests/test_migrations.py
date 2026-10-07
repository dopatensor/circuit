"""Migrations apply from scratch, match the models, and roll back cleanly."""

import uuid

import psycopg
import pytest
from alembic import command
from alembic.config import Config

from app.cli import ALEMBIC_INI
from tests.conftest import libpq_url


@pytest.fixture
def scratch_db_url(db_url):
    name = f"circuit_migcheck_{uuid.uuid4().hex[:8]}"
    admin = libpq_url(db_url).rsplit("/", 1)[0] + "/postgres"
    with psycopg.connect(admin, autocommit=True) as conn:
        try:
            conn.execute(f'CREATE DATABASE "{name}"')
        except psycopg.errors.InsufficientPrivilege:
            pytest.skip("database user cannot CREATE DATABASE")
    yield db_url.rsplit("/", 1)[0] + "/" + name
    with psycopg.connect(admin, autocommit=True) as conn:
        conn.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')


def _config(url: str) -> Config:
    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


def test_migrations_from_scratch_match_models_and_downgrade(scratch_db_url):
    cfg = _config(scratch_db_url)
    command.upgrade(cfg, "head")
    command.check(cfg)  # raises if the models and the migrated schema differ
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")


def test_spatial_and_vector_indexes_exist(db_url):
    with psycopg.connect(libpq_url(db_url)) as conn:
        rows = conn.execute(
            "SELECT indexname, indexdef FROM pg_indexes WHERE schemaname = 'public'"
        ).fetchall()
    defs = dict(rows)
    for name in ("ix_members_location", "ix_startups_location"):
        assert "USING gist" in defs[name]
    for name in ("ix_needs_embedding", "ix_offers_embedding"):
        assert "USING hnsw" in defs[name] and "vector_cosine_ops" in defs[name]
