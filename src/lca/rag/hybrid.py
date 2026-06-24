"""Hybrid retrieval: dense (embedding cosine) + keyword (BM25/FTS5), fused with
Reciprocal Rank Fusion.

RRF is robust to the two scorers being on different scales — it combines *ranks*,
not raw scores — which is exactly the property we want when mixing semantic and
lexical recall over code.
"""

from __future__ import annotations

from lca.observability.logging import get_logger
from lca.rag.embedder import Embedder
from lca.rag.retriever import ScoredChunk
from lca.rag.store import VectorStore

log = get_logger("rag.hybrid")


class HybridRetriever:
    def __init__(
        self,
        store: VectorStore,
        embedder: Embedder,
        *,
        k: int = 8,
        candidate_k: int = 20,
        rrf_k: int = 60,
    ) -> None:
        self._store = store
        self._embedder = embedder
        self._k = k
        self._candidate_k = candidate_k
        self._rrf_k = rrf_k

    async def retrieve(self, query: str, k: int | None = None) -> list[ScoredChunk]:
        top = k or self._k
        qvec = self._embedder.embed([query])[0]
        dense = self._store.search_dense(qvec, self._candidate_k)
        lexical = self._store.search_bm25(query, self._candidate_k)

        fused: dict[tuple[str, int, int], tuple[float, ScoredChunk]] = {}
        for ranked in (dense, lexical):
            for rank, chunk in enumerate(ranked):
                key = (chunk.path, chunk.start_line, chunk.end_line)
                contribution = 1.0 / (self._rrf_k + rank)
                prev = fused.get(key)
                score = (prev[0] if prev else 0.0) + contribution
                fused[key] = (score, chunk)

        ordered = sorted(fused.values(), key=lambda t: t[0], reverse=True)
        return [chunk.model_copy(update={"score": score}) for score, chunk in ordered[:top]]
