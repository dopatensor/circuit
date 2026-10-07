import os

# Point the app at the test database before any app module reads settings.
os.environ["ENV"] = "test"
os.environ["DEMO_AUTH"] = "false"
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://circuit:circuit@localhost:5432/circuit_test"
)

import httpx  # noqa: E402
import psycopg  # noqa: E402
import pytest  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from app.cli import migrate  # noqa: E402
from app.db import make_engine  # noqa: E402
from app.main import create_app  # noqa: E402

TEST_DB_URL = os.environ["DATABASE_URL"]


def libpq_url(url: str) -> str:
    """postgresql+psycopg://... -> postgresql://... (for plain psycopg connections)."""
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


@pytest.fixture(scope="session")
def db_url() -> str:
    """The migrated test database. Tests that need Postgres skip if it isn't running."""
    try:
        psycopg.connect(libpq_url(TEST_DB_URL), connect_timeout=3).close()
    except psycopg.OperationalError:
        pytest.skip("test database not running (start it with: docker compose up -d)")
    migrate(TEST_DB_URL)
    return TEST_DB_URL


@pytest.fixture
async def session(db_url):
    """A session that commits for real (seed tests need committed data)."""
    engine = make_engine(db_url)
    async with AsyncSession(engine, expire_on_commit=False) as s:
        yield s
    await engine.dispose()


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
