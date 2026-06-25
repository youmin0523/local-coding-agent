"""Self-consistency disagreement probe for difficulty routing.

A cheap signal: sample the fast model a couple of times and measure how much the
answers diverge. High divergence ⇒ the task is genuinely uncertain for the model,
so the router should escalate (bigger model, best-of-N, verification) even when the
keyword heuristic thought it was easy. Pure + decoupled from the provider (takes a
``sample_once`` callable) so the scoring logic is unit-testable without a model.
"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable

_WORD = re.compile(r"[0-9a-z]+")


def _tokens(text: str) -> set[str]:
    return set(_WORD.findall(text.lower()))


def disagreement_score(samples: list[str]) -> float:
    """``1 - mean pairwise Jaccard`` over sample token sets (0=identical, 1=disjoint)."""
    toks = [_tokens(s) for s in samples if s.strip()]
    if len(toks) < 2:
        return 0.0
    sims: list[float] = []
    for i in range(len(toks)):
        for j in range(i + 1, len(toks)):
            union = toks[i] | toks[j]
            sims.append(len(toks[i] & toks[j]) / len(union) if union else 1.0)
    avg = sum(sims) / len(sims) if sims else 1.0
    return round(1.0 - avg, 3)


async def probe_disagreement(sample_once: Callable[[], Awaitable[str]], *, k: int = 2) -> float:
    """Draw ``k`` samples and return their disagreement score (0..1)."""
    samples = [await sample_once() for _ in range(max(2, k))]
    return disagreement_score(samples)
