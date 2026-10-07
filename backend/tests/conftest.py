import asyncio
import os
import uuid

# Point the app at the test database before any app module reads settings.
os.environ["ENV"] = "test"
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://circuit:circuit@localhost:5432/circuit_test"
)

import httpx  # noqa: E402
import psycopg  # noqa: E402
import pytest  # noqa: E402
from sqlalchemy import delete  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from app.auth import issue_demo_token  # noqa: E402
from app.cli import migrate, seed  # noqa: E402
from app.config import Settings  # noqa: E402
from app.db import get_engine, make_engine  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models import Member  # noqa: E402

TEST_DB_URL = os.environ["DATABASE_URL"]


def libpq_url(url: str) -> str:
    """postgresql+psycopg://... -> postgresql://... (for plain psycopg connections)."""
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


def make_test_settings(**overrides) -> Settings:
    """Settings for tests: ignore the developer's .env file (no real API key etc.)."""
    values = {
        "env": "test",
        "database_url": TEST_DB_URL,
        "demo_auth": True,
        "anthropic_api_key": None,
        "jwks_url": None,
        "embedding_provider": "fake",
        "scheduler_enabled": False,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


@pytest.fixture(scope="session")
def db_url() -> str:
    """The migrated test database. Tests that need Postgres skip if it isn't running."""
    try:
        psycopg.connect(libpq_url(TEST_DB_URL), connect_timeout=3).close()
    except psycopg.OperationalError:
        pytest.skip("test database not running (start it with: docker compose up -d)")
    migrate(TEST_DB_URL)
    return TEST_DB_URL


@pytest.fixture(scope="session")
def seeded(db_url) -> str:
    """The test database reset to the demo seed (once per test run)."""
    asyncio.run(seed(db_url, make_test_settings(), reset=True))
    return db_url


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def session(db_url):
    """A session that commits for real (seed tests need committed data)."""
    engine = make_engine(db_url)
    async with AsyncSession(engine, expire_on_commit=False) as s:
        yield s
    await engine.dispose()


@pytest.fixture
def settings() -> Settings:
    return make_test_settings()


@pytest.fixture
def app(settings):
    return create_app(settings)


@pytest.fixture
async def client(app):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    # Each test runs in its own event loop; don't keep pooled connections across loops.
    await get_engine().dispose()


@pytest.fixture
def login(client, seeded):
    """login("ravi") -> Authorization headers for that seeded persona."""

    async def _login(persona: str) -> dict[str, str]:
        r = await client.post("/api/auth/demo/login", json={"persona": persona})
        assert r.status_code == 200, r.text
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    return _login


@pytest.fixture
async def make_member(seeded, settings):
    """Create throwaway members (removed after the test) and return their auth headers."""
    created: list[uuid.UUID] = []
    engine = make_engine(seeded)

    async def _make(role: str = "founder", level: int = 1, **fields) -> tuple[uuid.UUID, dict]:
        key = f"test-{uuid.uuid4().hex[:10]}"
        member = Member(
            auth_subject=f"demo:{key}",
            role=role,
            display_name=fields.pop("display_name", f"Test {key}"),
            verification_level=level,
            **fields,
        )
        async with AsyncSession(engine, expire_on_commit=False) as s:
            s.add(member)
            await s.commit()
        created.append(member.id)
        token, _ = issue_demo_token(settings, member)
        return member.id, {"Authorization": f"Bearer {token}"}

    yield _make
    async with AsyncSession(engine) as s:
        await s.execute(delete(Member).where(Member.id.in_(created)))
        await s.commit()
    await engine.dispose()
