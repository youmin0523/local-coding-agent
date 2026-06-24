"""Text embedders for RAG, run on CPU to keep all VRAM for the LLM.

Two implementations behind one Protocol:

* `HashingEmbedder` — a dependency-free, deterministic feature-hashing embedder.
  It needs no model download, so it is the default for tests and fully-offline
  use. Quality is modest but it makes the whole RAG pipeline runnable anywhere.
* `FastEmbedEmbedder` — wraps fastembed (e.g. bge-small) for real semantic
  quality; used when the optional ``rag`` extra is installed.

The agent depends only on the `Embedder` Protocol, so swapping is a config choice.
"""

from __future__ import annotations

import itertools
import math
import re
from typing import Protocol, runtime_checkable

_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")


@runtime_checkable
class Embedder(Protocol):
    dim: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


def _l2_normalize(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vec))
    if norm == 0.0:
        return vec
    return [x / norm for x in vec]


class HashingEmbedder:
    """Deterministic feature-hashing embedder over unigrams + bigrams."""

    def __init__(self, dim: int = 256) -> None:
        self.dim = dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(t) for t in texts]

    def _embed_one(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        tokens = [t.lower() for t in _TOKEN_RE.findall(text)]
        for tok in tokens:
            vec[hash(tok) % self.dim] += 1.0
        for a, b in itertools.pairwise(tokens):
            vec[hash(f"{a}~{b}") % self.dim] += 1.0
        return _l2_normalize(vec)


class FastEmbedEmbedder:
    """Real semantic embeddings via fastembed (optional ``rag`` extra)."""

    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5") -> None:
        from fastembed import TextEmbedding  # lazy: only when actually used

        self._model = TextEmbedding(model_name=model_name)
        # bge-small is 384-dim; probe to be exact.
        self.dim = len(next(iter(self._model.embed(["probe"]))))

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [list(map(float, v)) for v in self._model.embed(texts)]


def default_embedder() -> Embedder:
    """Prefer fastembed if installed; otherwise the dependency-free hashing one."""
    try:
        return FastEmbedEmbedder()
    except Exception:  # not installed / model unavailable → offline fallback
        return HashingEmbedder()
