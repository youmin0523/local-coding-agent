"""Map an estimated difficulty to a concrete compute plan.

* easy   → fast 7B, single pass, no verification (snappy).
* normal → brain 30B, single pass, verified.
* hard   → brain 30B, best-of-N, verified (more test-time compute).

Falls back to the fast model when the brain is unavailable.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from lca.routing.difficulty import Difficulty, estimate_difficulty


class RoutePlan(BaseModel):
    model: Literal["brain", "fast"]
    samples: int
    verify: bool
    difficulty: Difficulty


class Router:
    def __init__(self, *, brain_available: bool = True) -> None:
        self._brain = brain_available

    def _model(self) -> Literal["brain", "fast"]:
        return "brain" if self._brain else "fast"

    def plan(
        self, task: str, *, file_count: int = 0, disagreement: float | None = None
    ) -> RoutePlan:
        difficulty = estimate_difficulty(task, file_count=file_count, disagreement=disagreement)
        if difficulty == Difficulty.EASY:
            return RoutePlan(model="fast", samples=1, verify=False, difficulty=difficulty)
        if difficulty == Difficulty.NORMAL:
            return RoutePlan(model=self._model(), samples=1, verify=True, difficulty=difficulty)
        return RoutePlan(model=self._model(), samples=3, verify=True, difficulty=difficulty)
