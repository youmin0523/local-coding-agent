"""Estimate task difficulty to allocate test-time compute.

Cheap heuristics (length, hard/easy keywords, number of files in play) optionally
combined with a self-consistency *disagreement* signal from a quick fast-model
sampling. The point is to spend more compute (bigger model, more samples, harder
verification) only where it pays off — most turns are easy.
"""

from __future__ import annotations

from enum import StrEnum

_HARD = {
    "refactor",
    "architecture",
    "design",
    "migrate",
    "concurrency",
    "race condition",
    "optimize",
    "performance",
    "security",
    "root cause",
    "redesign",
    "debug",
    "why does",
    "distributed",
    "deadlock",
    "memory leak",
}
_EASY = {
    "rename",
    "typo",
    "format",
    "print",
    "hello world",
    "list",
    "show me",
    "what is",
    "add a comment",
    "lowercase",
    "uppercase",
}


class Difficulty(StrEnum):
    EASY = "easy"
    NORMAL = "normal"
    HARD = "hard"


def estimate_difficulty(
    task: str, *, file_count: int = 0, disagreement: float | None = None
) -> Difficulty:
    """Classify a task. ``disagreement`` (0..1) is optional self-consistency spread."""
    t = task.lower()
    score = 0
    score += min(len(t) // 240, 3)
    score += 2 * sum(1 for kw in _HARD if kw in t)
    score -= sum(1 for kw in _EASY if kw in t)
    score += min(file_count, 3)
    if disagreement is not None:
        score += round(disagreement * 4)
    if score <= 0:
        return Difficulty.EASY
    if score >= 4:
        return Difficulty.HARD
    return Difficulty.NORMAL
