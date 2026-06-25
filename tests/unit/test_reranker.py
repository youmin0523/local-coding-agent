"""Reranker hook in HybridRetriever (with a fake reranker; no model download)."""

from __future__ import annotations

from lca.rag.embedder import HashingEmbedder
from lca.rag.hybrid import HybridRetriever
from lca.rag.reranker import default_reranker
from lca.rag.retriever import ScoredChunk

_CHUNKS = [
    ScoredChunk(path="a.py", start_line=1, end_line=2, text="alpha"),
    ScoredChunk(path="b.py", start_line=1, end_line=2, text="beta"),
    ScoredChunk(path="c.py", start_line=1, end_line=2, text="gamma"),
]


class _FakeStore:
    def search_dense(self, qvec: list[float], k: int) -> list[ScoredChunk]:
        return _CHUNKS[:k]

    def search_bm25(self, query: str, k: int) -> list[ScoredChunk]:
        return _CHUNKS[:k]


class _ReverseReranker:
    def rerank(self, query: str, chunks: list[ScoredChunk], top: int) -> list[ScoredChunk]:
        return list(reversed(chunks))[:top]


def test_default_reranker_off_is_none():
    assert default_reranker(False) is None


async def test_reranker_reorders_results():
    plain = HybridRetriever(_FakeStore(), HashingEmbedder())
    reranked = HybridRetriever(_FakeStore(), HashingEmbedder(), reranker=_ReverseReranker())

    top_plain = (await plain.retrieve("q", k=2))[0].text
    top_reranked = (await reranked.retrieve("q", k=2))[0].text

    assert top_plain == "alpha"  # RRF keeps the original lead
    assert top_reranked == "gamma"  # reranker put the last candidate first
