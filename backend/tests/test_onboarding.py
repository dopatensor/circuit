"""Smart onboarding (F1): LLM suggestions limited to our lists, with manual fallback."""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import anthropic
import pytest
from sqlalchemy import select

from app.api import onboarding as onboarding_api
from app.models import Event
from app.onboarding import AnthropicSuggester, SuggestionsUnavailable, clean
from app.schemas import SuggestedItem, Suggestions
from app.seed.catalog import CAPABILITY_IDS, TRAIT_IDS

pytestmark = pytest.mark.anyio

BIO = (
    "I'm a final-year student who builds React frontends and Python APIs. "
    "Looking for an internship and someone to help me get better at system design."
)


# --- a fake Anthropic Messages API, so the real SDK code path runs without a key --------


@pytest.fixture
async def fake_api():
    state = {"requests": [], "status": 200, "stop_reason": "end_turn", "answer": None}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            length = int(self.headers["Content-Length"])
            state["requests"].append(json.loads(self.rfile.read(length)))
            if state["status"] != 200:
                body = {"type": "error", "error": {"type": "api_error", "message": "boom"}}
            else:
                body = {
                    "id": "msg_test",
                    "type": "message",
                    "role": "assistant",
                    "model": "claude-haiku-4-5-20251001",
                    "content": [{"type": "text", "text": json.dumps(state["answer"])}],
                    "stop_reason": state["stop_reason"],
                    "stop_sequence": None,
                    "usage": {"input_tokens": 1200, "output_tokens": 90},
                }
            data = json.dumps(body).encode()
            self.send_response(state["status"])
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    client = anthropic.AsyncAnthropic(
        api_key="test-key", base_url=f"http://127.0.0.1:{server.server_port}", max_retries=0
    )
    yield state, AnthropicSuggester(client, "claude-haiku-4-5-20251001")
    await client.close()
    server.shutdown()
    server.server_close()


GOOD_ANSWER = {
    "needs": [
        {"capability_id": "technical_architecture", "text": "Get better at system design"},
        {"capability_id": "hiring", "text": "Find an internship"},
    ],
    "offers": [{"capability_id": "frontend_development", "text": "React frontends"}],
    "skills": ["frontend_development", "backend_development", "frontend_development"],
    "traits": ["remote_first"],
}


async def test_sdk_request_is_constrained_to_our_lists(fake_api):
    state, suggester = fake_api
    state["answer"] = GOOD_ANSWER
    result = await suggester.suggest(BIO, "student")

    assert [n.capability_id for n in result.needs] == ["technical_architecture", "hiring"]
    assert result.skills == ["frontend_development", "backend_development"]  # de-duplicated

    (req,) = state["requests"]
    assert req["model"] == "claude-haiku-4-5-20251001"
    assert "<description>" in req["messages"][0]["content"]
    schema = req["output_config"]["format"]["schema"]
    text = json.dumps(schema)
    # Every capability and trait id is offered as an enum value, and nothing else is.
    enums = [set(v["enum"]) for v in _walk(schema) if "enum" in v]
    assert set(CAPABILITY_IDS) in enums and set(TRAIT_IDS) in enums
    assert '"additionalProperties": false' in text


def _walk(node):
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from _walk(v)
    elif isinstance(node, list):
        for v in node:
            yield from _walk(v)


async def test_refusal_or_error_means_unavailable(fake_api):
    state, suggester = fake_api
    state["answer"] = GOOD_ANSWER
    state["stop_reason"] = "refusal"
    with pytest.raises(SuggestionsUnavailable):
        await suggester.suggest(BIO, None)
    state["stop_reason"] = "end_turn"
    state["status"] = 500
    with pytest.raises(SuggestionsUnavailable):
        await suggester.suggest(BIO, None)


def test_clean_drops_unknown_ids_and_trims():
    raw = Suggestions(
        needs=[SuggestedItem(capability_id="time_travel", text="x")]
        + [
            SuggestedItem(capability_id=c, text="  lots   of   space " * 30)
            for c in sorted(CAPABILITY_IDS)[:8]
        ],
        offers=[],
        skills=["backend_development", "underwater_basket_weaving"],
        traits=["vibes", "b2b"],
    )
    out = clean(raw, role="founder")
    assert len(out.needs) == 5 and all(n.capability_id in CAPABILITY_IDS for n in out.needs)
    assert all(len(n.text) <= 200 and "  " not in n.text for n in out.needs)
    assert out.skills == []  # skills are only suggested for students
    assert out.traits == ["b2b"]


# --- the endpoints ------------------------------------------------------------------------


async def test_without_api_key_falls_back_to_manual_pickers(client, make_member):
    _, headers = await make_member(level=0)  # onboarding works before verification
    r = await client.post("/api/onboarding/suggest", headers=headers, json={"text": BIO})
    assert r.status_code == 200
    assert r.json() == {
        "source": "manual",
        "fallback_reason": "no_api_key",
        "suggestions": {"needs": [], "offers": [], "skills": [], "traits": []},
    }


async def test_llm_suggestions_and_failure_fallback(client, make_member, monkeypatch, session):
    member_id, headers = await make_member(role="student", level=0)

    class Fake:
        fail = False

        async def suggest(self, text, role):
            if self.fail:
                raise SuggestionsUnavailable
            return clean(Suggestions.model_validate(GOOD_ANSWER), role)

    fake = Fake()
    monkeypatch.setattr(onboarding_api, "get_suggester", lambda settings: fake)
    r = await client.post(
        "/api/onboarding/suggest", headers=headers, json={"text": BIO, "role": "student"}
    )
    body = r.json()
    assert body["source"] == "llm" and body["fallback_reason"] is None
    assert body["suggestions"]["offers"][0]["capability_id"] == "frontend_development"

    fake.fail = True
    r = await client.post("/api/onboarding/suggest", headers=headers, json={"text": BIO})
    assert r.json()["source"] == "manual" and r.json()["fallback_reason"] == "llm_unavailable"

    events = (
        await session.scalars(
            select(Event).where(Event.actor_id == member_id, Event.type == "onboarding.suggested")
        )
    ).all()
    assert len(events) == 2
    assert all("React" not in json.dumps(e.payload) for e in events)  # no free text stored


async def test_text_length_is_bounded(client, make_member):
    _, headers = await make_member(level=0)
    r = await client.post("/api/onboarding/suggest", headers=headers, json={"text": "x" * 4001})
    assert r.status_code == 422


async def test_confirm_replaces_selection(client, make_member):
    _, headers = await make_member(role="student", level=1)
    first = {
        "bio": "Student builder.",
        "needs": [{"capability_id": "hiring", "text": "Internship"}],
        "offers": [{"capability_id": "frontend_development", "text": "React"}],
        "skills": [{"capability_id": "frontend_development", "level": 3}],
        "trait_ids": ["remote_first"],
    }
    me = (await client.post("/api/onboarding/confirm", headers=headers, json=first)).json()
    assert me["bio"] == "Student builder."
    assert [n["capability_id"] for n in me["needs"]] == ["hiring"]
    assert me["skills"] == [{"capability_id": "frontend_development", "level": 3}]

    second = {"needs": [{"capability_id": "technical_architecture"}], "trait_ids": []}
    me = (await client.post("/api/onboarding/confirm", headers=headers, json=second)).json()
    assert [n["capability_id"] for n in me["needs"]] == ["technical_architecture"]
    assert me["offers"] == [] and me["skills"] == [] and me["trait_ids"] == []
    assert me["bio"] == "Student builder."  # untouched when not sent


async def test_confirm_rejects_ids_outside_the_lists(client, make_member):
    _, headers = await make_member(level=1)
    r = await client.post(
        "/api/onboarding/confirm", headers=headers, json={"trait_ids": ["made_up"]}
    )
    assert r.status_code == 422


async def test_confirm_ignores_skills_for_non_students(client, make_member):
    _, headers = await make_member(role="mentor", level=1)
    r = await client.post(
        "/api/onboarding/confirm",
        headers=headers,
        json={"skills": [{"capability_id": "marketing", "level": 3}]},
    )
    assert r.json()["skills"] == []
