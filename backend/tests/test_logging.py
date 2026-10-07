import json

import pytest
from fastapi import Request

pytestmark = pytest.mark.anyio


def request_lines(output: str) -> list[dict]:
    lines = [json.loads(line) for line in output.splitlines() if line.startswith("{")]
    return [line for line in lines if line.get("event") == "request"]


async def test_one_json_line_per_request_with_required_fields(client, capsys):
    capsys.readouterr()
    r = await client.get("/health")
    (line,) = request_lines(capsys.readouterr().out)
    assert {"request_id", "method", "path", "status", "duration_ms", "user_id"} <= set(line)
    assert line["method"] == "GET"
    assert line["path"] == "/health"
    assert line["status"] == 200
    assert line["request_id"] == r.headers["X-Request-ID"]
    assert line["user_id"] is None


async def test_query_string_is_never_logged(client, capsys):
    capsys.readouterr()
    await client.get("/health?email=asha@example.com&token=abc123")
    out = capsys.readouterr().out
    assert "asha@example.com" not in out
    assert "abc123" not in out
    (line,) = request_lines(out)
    assert line["path"] == "/health"


async def test_unsafe_incoming_request_id_is_replaced(client, capsys):
    capsys.readouterr()
    r = await client.get("/health", headers={"X-Request-ID": "priya@example.com"})
    assert r.headers["X-Request-ID"] != "priya@example.com"
    assert "priya@example.com" not in capsys.readouterr().out


async def test_safe_incoming_request_id_is_kept(client):
    r = await client.get("/health", headers={"X-Request-ID": "demo-123"})
    assert r.headers["X-Request-ID"] == "demo-123"


async def test_user_id_set_by_endpoint_is_logged(app, client, capsys):
    @app.get("/_whoami")
    async def whoami(request: Request):
        request.state.user_id = "member-42"
        return {}

    capsys.readouterr()
    await client.get("/_whoami")
    (line,) = request_lines(capsys.readouterr().out)
    assert line["user_id"] == "member-42"


async def test_unhandled_error_is_logged_as_500(app, capsys):
    import httpx

    @app.get("/_boom")
    async def boom():
        raise RuntimeError("boom")

    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        capsys.readouterr()
        r = await c.get("/_boom")
    assert r.status_code == 500
    lines = request_lines(capsys.readouterr().out)
    assert [line["status"] for line in lines] == [500]
