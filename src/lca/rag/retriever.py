"""Retrieval interface and the scored-chunk type shared across RAG and the agent.

Defined here (rather than alongside the concrete store) so the agent core can
depend on the interface without importing the heavier RAG implementation. The
concrete `HybridRetriever` (BM25 + dense + RRF over sqlite-vec) is added in M3.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel


class ScoredChunk(BaseModel):
    """A retrieved code chunk with provenance, for citeable grounding."""

    path: str
    start_line: int
    end_line: int
    text: str
    score: float = 0.0

    def render(self) -> str:
        return f"# {self.path}:{self.start_line}-{self.end_line}\n{self.text}"


@runtime_checkable
class Retriever(Protocol):
    async def retrieve(self, query: str, k: int = 8) -> list[ScoredChunk]: ...
