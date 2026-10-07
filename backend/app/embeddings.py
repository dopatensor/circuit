"""Text embeddings behind a small interface (Phase 4).

An embedding turns a sentence into 384 numbers so that sentences with similar meaning
end up close together. We embed every need and offer ("Marketing: explain diagnostics
to hospital lab heads") so matching can find helpers whose words fit, even when they
picked a different capability chip.

- FastEmbedProvider: the real model (BAAI/bge-small-en-v1.5), run locally on CPU.
- FakeEmbeddingProvider: deterministic and instant, for tests: texts that share words
  get similar vectors, which is all the tests need.
"""

import hashlib
import math
import re
from functools import lru_cache
from typing import Protocol

import anyio
import structlog
from sqlalchemy import select, update

from app.config import Settings
from app.models import EMBEDDING_DIM, Capability, Need, Offer

log = structlog.get_logger("embeddings")


class EmbeddingProvider(Protocol):
    dim: int

    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class FakeEmbeddingProvider:
    """Hashes each word into one of 384 buckets, then normalises (unit length)."""

    dim = EMBEDDING_DIM

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._one(t) for t in texts]

    def _one(self, text: str) -> list[float]:
        v = [0.0] * self.dim
        for word in re.findall(r"[a-z0-9]+", text.lower()):
            h = int.from_bytes(hashlib.sha256(word.encode()).digest()[:4], "big")
            v[h % self.dim] += 1.0
        norm = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / norm for x in v]


class FastEmbedProvider:
    dim = EMBEDDING_DIM
    MODEL = "BAAI/bge-small-en-v1.5"

    def __init__(self, cache_dir: str):
        self.cache_dir = cache_dir
        self._model = None

    def _embed_sync(self, texts: list[str]) -> list[list[float]]:
        if self._model is None:
            from fastembed import TextEmbedding  # heavy import, only when needed

            self._model = TextEmbedding(self.MODEL, cache_dir=self.cache_dir)
        return [v.tolist() for v in self._model.embed(texts, batch_size=64)]

    async def embed(self, texts: list[str]) -> list[list[float]]:
        # The model is CPU-bound; run it in a worker thread so the API stays responsive.
        return await anyio.to_thread.run_sync(self._embed_sync, texts)


@lru_cache(maxsize=2)
def _fastembed(cache_dir: str) -> FastEmbedProvider:
    return FastEmbedProvider(cache_dir)


def get_embedding_provider(settings: Settings) -> EmbeddingProvider:
    if settings.embedding_provider == "fake":
        return FakeEmbeddingProvider()
    return _fastembed(settings.embedding_cache_dir)


def embedding_text(capability_name: str, text: str) -> str:
    return f"{capability_name}: {text}".strip().rstrip(":")


async def embed_pending(session, provider: EmbeddingProvider, batch: int = 256) -> int:
    """Embed every active need and offer that has no embedding yet. Returns the count."""
    names = dict((await session.execute(select(Capability.id, Capability.name))).all())
    done = 0
    for model in (Need, Offer):
        rows = (
            await session.execute(
                select(model.id, model.capability_id, model.text).where(
                    model.embedding.is_(None), model.active
                )
            )
        ).all()
        for i in range(0, len(rows), batch):
            chunk = rows[i : i + batch]
            vectors = await provider.embed(
                [embedding_text(names[r.capability_id], r.text) for r in chunk]
            )
            # Bulk "UPDATE ... WHERE id = ..." for the whole chunk.
            await session.execute(
                update(model),
                [{"id": r.id, "embedding": v} for r, v in zip(chunk, vectors, strict=True)],
            )
            done += len(chunk)
    log.info("embedded", count=done, provider=type(provider).__name__)
    return done
