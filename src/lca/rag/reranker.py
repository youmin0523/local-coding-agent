"""Optional cross-encoder reranker for retrieval precision.

Bi-encoder retrieval (embedding cosine) + BM25 fused by RRF gives good recall, but
the top results aren't always in the best *order*. A cross-encoder scores each
(query, chunk) pair jointly and reorders the shortlist — higher precision at the
top, which is what the agent actually reads. Optional and off by default: enabling
it downloads a small model on first use, with a graceful no-op fallback offline.
"""

from __future__ import annotations

from typing import Protocol

from lca.observability.logging import get_logger
from lca.rag.retriever import ScoredChunk

log = get_logger("rag.reranker")

_DEFAULT_MODEL = "Xenova/ms-marco-MiniLM-L-6-v2"


class Reranker(Protocol):
    def rerank(self, query: str, chunks: list[ScoredChunk], top: int) -> list[ScoredChunk]: ...


class FastEmbedReranker:
    """Cross-encoder reranker backed by fastembed's TextCrossEncoder (CPU)."""

    def __init__(self, model_name: str = _DEFAULT_MODEL) -> None:
        from fastembed.rerank.cross_encoder import TextCrossEncoder

        self._model = TextCrossEncoder(model_name=model_name)

    def rerank(self, query: str, chunks: list[ScoredChunk], top: int) -> list[ScoredChunk]:
        if not chunks:
            return chunks
        scores = list(self._model.rerank(query, [c.text for c in chunks]))
        ranked = sorted(zip(scores, chunks, strict=True), key=lambda t: t[0], reverse=True)
        return [chunk.model_copy(update={"score": float(score)}) for score, chunk in ranked[:top]]


def default_reranker(enabled: bool = False) -> Reranker | None:
    """A reranker if ``enabled`` and the model loads; otherwise None (no reranking)."""
    if not enabled:
        return None
    try:
        return FastEmbedReranker()
    except Exception:  # dependency/model unavailable → degrade to no reranking
        log.warning("rag.reranker_unavailable")
        return None
