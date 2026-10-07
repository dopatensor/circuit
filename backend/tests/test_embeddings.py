import math
import os

import pytest
from sqlalchemy import func, select

from app.embeddings import FakeEmbeddingProvider, FastEmbedProvider, embed_pending
from app.models import Need, Offer

pytestmark = pytest.mark.anyio


def cos(a, b):
    return sum(x * y for x, y in zip(a, b, strict=True))


async def test_fake_provider_is_deterministic_normalised_and_word_aware():
    p = FakeEmbeddingProvider()
    a, b, c = await p.embed(
        ["marketing to hospital labs", "marketing for hospital buyers", "rust firmware"]
    )
    assert len(a) == 384 and math.isclose(sum(x * x for x in a), 1.0, rel_tol=1e-9)
    assert (await p.embed(["marketing to hospital labs"]))[0] == a
    assert cos(a, b) > cos(a, c)


async def test_embed_pending_fills_missing_and_is_idempotent(session, seeded):
    await session.execute(Need.__table__.update().values(embedding=None))
    await session.commit()
    n = await embed_pending(session, FakeEmbeddingProvider())
    await session.commit()
    assert n > 0
    missing = await session.scalar(
        select(func.count()).select_from(Need).where(Need.embedding.is_(None), Need.active)
    )
    assert missing == 0
    assert await embed_pending(session, FakeEmbeddingProvider()) == 0
    missing_offers = await session.scalar(
        select(func.count()).select_from(Offer).where(Offer.embedding.is_(None), Offer.active)
    )
    assert missing_offers == 0


@pytest.mark.skipif(
    not os.environ.get("RUN_MODEL_TESTS"), reason="downloads the real model; set RUN_MODEL_TESTS=1"
)
async def test_real_model_puts_related_sentences_closer(tmp_path):
    p = FastEmbedProvider(str(tmp_path))
    a, b, c = await p.embed(
        [
            "Marketing: explain diagnostics to hospital lab heads",
            "Technical marketing: position complex products for expert buyers",
            "Embedded hardware: firmware for drones",
        ]
    )
    assert len(a) == 384 and cos(a, b) > cos(a, c)
