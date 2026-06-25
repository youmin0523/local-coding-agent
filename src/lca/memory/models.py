"""Value types for experience memory."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

MemoryKind = Literal["episodic", "strategy", "preference"]


class MemoryItem(BaseModel):
    """One remembered experience.

    * ``episodic`` — a concrete verified task→solution.
    * ``strategy`` — a distilled lesson ("when X, do Y").
    * ``preference`` — a captured user preference (e.g. an approval pattern).
    """

    kind: MemoryKind
    title: str
    content: str
    source: str = ""
    score: float = 0.0

    def render(self) -> str:
        return f"[{self.kind}] {self.title}: {self.content}"
