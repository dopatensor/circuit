import pytest

from app.db import get_engine, make_engine

pytestmark = pytest.mark.anyio


async def test_health_ok(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
    assert r.headers["X-Request-ID"]


async def test_health_deps_reports_postgres_and_extensions(app, client):
    engine = make_engine(app_database_url())
    app.dependency_overrides[get_engine] = lambda: engine
    try:
        r = await client.get("/health/deps")
    finally:
        await engine.dispose()
    body = r.json()
    if not body["checks"]["postgres"]["ok"]:
        pytest.skip("test database not running (start it with: docker compose up -d)")
    assert r.status_code == 200
    assert body["status"] == "ok"
    assert set(body["checks"]) == {"postgres", "postgis", "vector"}


async def test_health_deps_returns_503_when_db_unreachable(app, client):
    engine = make_engine("postgresql+psycopg://nobody:secret@127.0.0.1:1/nope", connect_timeout_s=1)
    app.dependency_overrides[get_engine] = lambda: engine
    try:
        r = await client.get("/health/deps")
    finally:
        await engine.dispose()
    assert r.status_code == 503
    body = r.json()
    assert body["status"] == "degraded"
    assert body["checks"]["postgres"]["ok"] is False
    assert "secret" not in r.text  # connection details never leak


def app_database_url() -> str:
    import os

    return os.environ["DATABASE_URL"]
