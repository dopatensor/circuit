"""The frontend's typed API client is generated from frontend/openapi.json. If an
endpoint or schema changes, regenerate it: `cd frontend && npm run gen:api`."""

from app.cli import openapi_json
from app.config import REPO_ROOT


def test_frontend_openapi_copy_is_current():
    committed = (REPO_ROOT / "frontend" / "openapi.json").read_text(encoding="utf-8")
    assert committed.strip() == openapi_json().strip(), (
        "frontend/openapi.json is stale: run `cd frontend && npm run gen:api`"
    )
