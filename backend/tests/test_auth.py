"""Demo logins, provider (JWKS) tokens, and verification-level checks."""

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Annotated

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import Depends

from app.auth import CurrentUser, require_level
from app.config import DEV_DEMO_SECRET
from app.main import create_app
from app.seed.stories import DEMO_PERSONAS
from tests.conftest import make_test_settings

pytestmark = pytest.mark.anyio

ISSUER = "https://auth.example.test"
AUDIENCE = "circuit"


# --- a fake identity provider: an RSA key pair and a JWKS endpoint ----------------------


@pytest.fixture(scope="module")
def provider():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
    jwk.update({"kid": "test-key", "use": "sig", "alg": "RS256"})
    body = json.dumps({"keys": [jwk]}).encode()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    def sign(sub: str, signing_key=key, **claims) -> str:
        payload = {"sub": sub, "iss": ISSUER, "aud": AUDIENCE, "exp": int(time.time()) + 600}
        payload.update(claims)
        return jwt.encode(payload, signing_key, algorithm="RS256", headers={"kid": "test-key"})

    yield {"url": f"http://127.0.0.1:{server.server_port}/jwks.json", "sign": sign}
    server.shutdown()
    server.server_close()


@pytest.fixture
def settings(provider):
    return make_test_settings(jwks_url=provider["url"], jwt_issuer=ISSUER, jwt_audience=AUDIENCE)


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# --- demo personas ---------------------------------------------------------------------


async def test_personas_are_listed_with_their_stories(client, seeded):
    r = await client.get("/api/auth/demo/personas")
    assert r.status_code == 200
    personas = {p["key"]: p for p in r.json()}
    assert list(personas) == [key for key, _, _ in DEMO_PERSONAS]
    assert personas["ravi"]["role"] == "student"
    assert personas["nandini"]["role"] == "partner_admin"
    assert (personas["asha"]["story_number"], personas["asha"]["story_title"]) == (
        2, "Exchange circuit"
    )  # fmt: skip
    numbers = [p["story_number"] for p in personas.values()]
    assert numbers == sorted(numbers) and set(numbers) == {1, 2, 3, 4, 5}


async def test_demo_login_then_me(client, login):
    headers = await login("meera")
    r = await client.get("/api/auth/me", headers=headers)
    body = r.json()
    assert body["has_profile"] and body["is_demo"]
    assert body["member"]["display_name"] == "Dr. Meera Iyer"


async def test_unknown_persona_is_404(client, seeded):
    r = await client.post("/api/auth/demo/login", json={"persona": "nobody"})
    assert r.status_code == 404


async def test_demo_endpoints_do_not_exist_without_demo_auth(seeded):
    app = create_app(make_test_settings(demo_auth=False))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        assert (await c.get("/api/auth/demo/personas")).status_code == 404
        assert (await c.post("/api/auth/demo/login", json={"persona": "ravi"})).status_code == 404


async def test_demo_token_rejected_when_demo_auth_off(seeded, login, client):
    headers = await login("ravi")
    app = create_app(make_test_settings(demo_auth=False))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        assert (await c.get("/api/members/me", headers=headers)).status_code == 401


# --- bad tokens ------------------------------------------------------------------------


@pytest.mark.parametrize(
    "token",
    [
        "not-a-jwt",
        jwt.encode({"sub": "demo:ravi", "iss": "circuit-demo", "exp": 1}, DEV_DEMO_SECRET),
        jwt.encode(
            {"sub": "demo:ravi", "iss": "circuit-demo", "exp": time.time() + 600}, "wrong" * 8
        ),
        jwt.encode(
            {"sub": "demo:ravi", "iss": "circuit-demo", "exp": time.time() + 600},
            key=None,
            algorithm="none",
        ),
        jwt.encode(
            {"sub": "user_x", "iss": "circuit-demo", "exp": time.time() + 600}, DEV_DEMO_SECRET
        ),
    ],
    ids=["garbage", "expired", "wrong-secret", "alg-none", "non-demo-subject"],
)
async def test_bad_tokens_are_401(client, seeded, token):
    r = await client.get("/api/members/me", headers=bearer(token))
    assert r.status_code == 401
    assert r.headers["WWW-Authenticate"] == "Bearer"


async def test_missing_token_is_401(client, seeded):
    assert (await client.get("/api/members/me")).status_code == 401


# --- provider (JWKS) tokens -------------------------------------------------------------


async def test_provider_token_signup_flow(client, provider, seeded):
    token = provider["sign"]("user_signup_1", verification_level=1)
    me = (await client.get("/api/auth/me", headers=bearer(token))).json()
    assert me == {
        "subject": "user_signup_1",
        "is_demo": False,
        "has_profile": False,
        "member": None,
    }
    # No profile yet: profile endpoints say so.
    assert (await client.get("/api/members/me", headers=bearer(token))).status_code == 403

    r = await client.post(
        "/api/members/me",
        headers=bearer(token),
        json={
            "role": "student",
            "display_name": "New Student",
            "college": "City Engineering College",
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["verification_level"] == 1  # provider said the email is verified
    assert (await client.post("/api/members/me", headers=bearer(token), json={
        "role": "student", "display_name": "Again"})).status_code == 409  # fmt: skip
    assert (await client.delete("/api/members/me", headers=bearer(token))).status_code == 204


async def test_provider_token_cannot_claim_a_higher_level_or_admin_role(client, provider, seeded):
    token = provider["sign"]("user_greedy", verification_level=3, role="partner_admin")
    r = await client.post(
        "/api/members/me", headers=bearer(token), json={"role": "founder", "display_name": "G"}
    )
    assert r.json()["verification_level"] == 1 and r.json()["role"] == "founder"
    await client.delete("/api/members/me", headers=bearer(token))
    r = await client.post(
        "/api/members/me",
        headers=bearer(token),
        json={"role": "partner_admin", "display_name": "G"},
    )
    assert r.status_code == 422


@pytest.mark.parametrize(
    "claims",
    [{"aud": "someone-else"}, {"iss": "https://evil.example"}, {"exp": int(time.time()) - 10}],
    ids=["wrong-audience", "wrong-issuer", "expired"],
)
async def test_provider_token_claims_are_checked(client, provider, seeded, claims):
    token = provider["sign"]("user_claims", **claims)
    assert (await client.get("/api/auth/me", headers=bearer(token))).status_code == 401


async def test_provider_token_signed_by_another_key_is_rejected(client, provider, seeded):
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    token = provider["sign"]("user_forged", signing_key=other)
    assert (await client.get("/api/auth/me", headers=bearer(token))).status_code == 401


async def test_provider_cannot_impersonate_a_demo_persona(client, provider, seeded):
    token = provider["sign"]("demo:nandini")
    assert (await client.get("/api/members/me", headers=bearer(token))).status_code == 401


# --- verification levels -----------------------------------------------------------------


async def test_require_level(app, client, make_member):
    @app.get("/_needs_level_2")
    async def protected(user: Annotated[CurrentUser, Depends(require_level(2))]):
        return {"ok": True}

    _, level1 = await make_member(level=1)
    _, level2 = await make_member(level=2)
    r = await client.get("/_needs_level_2", headers=level1)
    assert r.status_code == 403
    assert "level 2" in r.json()["detail"]
    assert (await client.get("/_needs_level_2", headers=level2)).status_code == 200


async def test_level_0_cannot_browse_but_can_edit_own_profile(client, make_member):
    _, headers = await make_member(level=0)
    assert (await client.get("/api/members", headers=headers)).status_code == 403
    assert (await client.get("/api/startups", headers=headers)).status_code == 403
    assert (await client.get("/api/members/me", headers=headers)).status_code == 200


async def test_request_log_includes_user_id(client, login, capsys):
    headers = await login("ravi")
    capsys.readouterr()
    me = (await client.get("/api/members/me", headers=headers)).json()
    lines = [json.loads(x) for x in capsys.readouterr().out.splitlines() if x.startswith("{")]
    request_lines = [x for x in lines if x.get("event") == "request"]
    assert request_lines[-1]["user_id"] == me["id"]
    assert "Ravi" not in json.dumps(request_lines)
