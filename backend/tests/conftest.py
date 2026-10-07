import os

# Point the app at the test database before any app module reads settings.
os.environ["ENV"] = "test"
os.environ["DEMO_AUTH"] = "false"
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://circuit:circuit@localhost:5432/circuit_test"
)

import httpx  # noqa: E402
import pytest  # noqa: E402

from app.main import create_app  # noqa: E402


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
