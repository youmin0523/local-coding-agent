"""The verification gate — combines judge votes (and execution signals) into a
single `Verdict`, and decides deliver vs. abstain.

The gate is the spine of the "only confident answers reach the user" guarantee:
an answer is delivered as ``pass`` only when a majority of diverse judges agree;
otherwise it is ``uncertain`` (abstain) or ``fail``. Execution results, when
provided, dominate — a failing test makes the verdict ``fail`` regardless of what
the judges believe.
"""

from __future__ import annotations

import asyncio
from typing import Protocol, runtime_checkable

from lca.providers.base import LLMProvider
from lca.verification.judges import LENSES, Judge, LLMJudge
from lca.verification.models import JudgeVote, Verdict, VerdictKind


@runtime_checkable
class Verifier(Protocol):
    async def verify_answer(
        self, task: str, answer: str, *, execution_passed: bool | None = None
    ) -> Verdict | None: ...


class VerificationGate:
    def __init__(self, judges: list[Judge], *, pass_threshold: float = 0.6) -> None:
        self._judges = judges
        self._pass_threshold = pass_threshold

    async def verify_answer(
        self, task: str, answer: str, *, execution_passed: bool | None = None
    ) -> Verdict:
        votes = await asyncio.gather(*(j.judge(task, answer) for j in self._judges))
        return self._combine(list(votes), execution_passed)

    def _combine(self, votes: list[JudgeVote], execution_passed: bool | None) -> Verdict:
        signals = [
            f"{v.lens}: {'ok' if v.passed else 'concern'} "
            f"({v.confidence:.2f}) {v.rationale}".strip()
            for v in votes
        ]
        # Execution is the dominant, un-fabricatable signal.
        if execution_passed is False:
            return Verdict(
                verdict="fail",
                confidence=0.95,
                rationale="Execution checks failed.",
                signals=signals,
            )

        if not votes:
            base = 1.0 if execution_passed else 0.0
            return Verdict(
                verdict="pass" if execution_passed else "uncertain",
                confidence=base,
                rationale="No judges configured.",
                signals=signals,
            )

        ratio = sum(1 for v in votes if v.passed) / len(votes)
        confidence = sum(v.confidence for v in votes if v.passed) / len(votes)
        if execution_passed:
            confidence = max(confidence, 0.8)

        verdict: VerdictKind
        if ratio >= self._pass_threshold:
            verdict = "pass"
        elif ratio <= (1.0 - self._pass_threshold):
            verdict = "fail"
        else:
            verdict = "uncertain"
        return Verdict(
            verdict=verdict,
            confidence=round(confidence, 3),
            rationale=f"{sum(1 for v in votes if v.passed)}/{len(votes)} judges passed.",
            signals=signals,
        )


def build_llm_gate(
    provider: LLMProvider,
    model: str,
    *,
    lenses: list[tuple[str, str]] | None = None,
    pass_threshold: float = 0.6,
) -> VerificationGate:
    judges: list[Judge] = [
        LLMJudge(provider, model, lens, instruction) for lens, instruction in (lenses or LENSES)
    ]
    return VerificationGate(judges, pass_threshold=pass_threshold)
