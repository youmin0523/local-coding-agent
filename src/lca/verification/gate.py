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
from lca.verification.adversary import Adversary, LLMAdversary
from lca.verification.judges import LENSES, Judge, LLMJudge
from lca.verification.models import JudgeVote, Verdict, VerdictKind


@runtime_checkable
class Verifier(Protocol):
    async def verify_answer(
        self, task: str, answer: str, *, execution_passed: bool | None = None
    ) -> Verdict | None: ...


# Below this mean judge confidence, a judges-only "pass" becomes an abstention.
_MIN_PASS_CONFIDENCE = 0.5


class VerificationGate:
    def __init__(
        self,
        judges: list[Judge],
        *,
        pass_threshold: float = 0.6,
        adversary: Adversary | None = None,
    ) -> None:
        self._judges = judges
        self._pass_threshold = pass_threshold
        self._adversary = adversary

    async def verify_answer(
        self, task: str, answer: str, *, execution_passed: bool | None = None
    ) -> Verdict:
        # Run the lens judges and the adversarial reviewer concurrently (the hidden
        # debate): the judges score the answer while the adversary tries to break it.
        async def _no_objection() -> str | None:
            return None

        votes, objection = await asyncio.gather(
            asyncio.gather(*(j.judge(task, answer) for j in self._judges)),
            self._adversary.review(task, answer) if self._adversary else _no_objection(),
        )
        return self._combine(list(votes), execution_passed, objection)

    def _combine(
        self,
        votes: list[JudgeVote],
        execution_passed: bool | None,
        objection: str | None = None,
    ) -> Verdict:
        signals = [
            f"{v.lens}: {'ok' if v.passed else 'concern'} "
            f"({v.confidence:.2f}) {v.rationale}".strip()
            for v in votes
        ]
        # The adversary's objection leads the signals so the self-repair pass targets it.
        if objection:
            signals.insert(0, f"adversary: {objection}")
        # Execution is the dominant, un-fabricatable signal — it OVERRIDES the judges
        # in both directions: failing checks can't be argued into a pass, and passing
        # checks can't be argued into an abstain by harsh/split judges.
        if execution_passed is False:
            return Verdict(
                verdict="fail",
                confidence=0.95,
                rationale="Execution checks failed.",
                signals=signals,
            )
        if execution_passed is True:
            return Verdict(
                verdict="pass",
                confidence=0.9,
                rationale="Execution checks passed.",
                signals=signals,
            )

        # No execution oracle → rely on the judges.
        if not votes:
            return Verdict(
                verdict="uncertain",
                confidence=0.0,
                rationale="No execution signal and no judges.",
                signals=signals,
            )

        ratio = sum(1 for v in votes if v.passed) / len(votes)
        passed_conf = [v.confidence for v in votes if v.passed]
        confidence = sum(passed_conf) / len(votes) if passed_conf else 0.0

        verdict: VerdictKind
        if ratio >= self._pass_threshold:
            # Enough judges pass — but abstain if their confidence is weak. A
            # low-confidence, execution-ungrounded answer is not a confident pass.
            verdict = "pass" if confidence >= _MIN_PASS_CONFIDENCE else "uncertain"
        elif ratio <= (1.0 - self._pass_threshold):
            verdict = "fail"
        else:
            verdict = "uncertain"
        rationale = f"{sum(1 for v in votes if v.passed)}/{len(votes)} judges passed."
        # An unrefuted adversarial objection blocks a judges-only pass: the answer must
        # survive the repair → re-verify round before it can be delivered as correct.
        if objection and verdict == "pass":
            verdict = "uncertain"
            rationale += " Adversary raised an unresolved objection."
        return Verdict(
            verdict=verdict,
            confidence=round(confidence, 3),
            rationale=rationale,
            signals=signals,
        )


def build_llm_gate(
    provider: LLMProvider,
    model: str,
    *,
    lenses: list[tuple[str, str]] | None = None,
    pass_threshold: float = 0.6,
    adversarial: bool = True,
) -> VerificationGate:
    judges: list[Judge] = [
        LLMJudge(provider, model, lens, instruction) for lens, instruction in (lenses or LENSES)
    ]
    adversary = LLMAdversary(provider, model) if adversarial else None
    return VerificationGate(judges, pass_threshold=pass_threshold, adversary=adversary)
