"""The scorer must agree with the hand-labelled pairs in tests/eval/pairs.json."""

import json

import pytest

from app.matching.evaluate import PAIRS_FILE, evaluate, summary
from tests.conftest import make_test_settings

pytestmark = pytest.mark.anyio


def test_pairs_file_is_well_formed():
    doc = json.loads(PAIRS_FILE.read_text())
    pairs = doc["pairs"]
    assert 45 <= len(pairs) <= 60
    assert {p["label"] for p in pairs} == {"good", "bad"}
    assert all(p["why"] for p in pairs)
    keys = [(p["member"], p["candidate"]["key"]) for p in pairs]
    assert len(keys) == len(set(keys))


async def test_scorer_agrees_with_labels(session, seeded):
    s = summary(await evaluate(session, make_test_settings()))
    assert s["agreement"] >= 0.85, s
    assert s["ranking"] >= 0.85, s
