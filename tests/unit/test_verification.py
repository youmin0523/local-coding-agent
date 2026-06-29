"""Verification gate: vote combination, judge parsing, consensus."""

from __future__ import annotations

from lca.providers.fake import FakeProvider, text_chunks
from lca.verification.adversary import LLMAdversary
from lca.verification.consensus import select_by_consensus
from lca.verification.gate import VerificationGate
from lca.verification.judges import LLMJudge
from lca.verification.models import JudgeVote


class _FakeJudge:
    def __init__(self, lens: str, passed: bool, confidence: float = 0.9) -> None:
        self.lens = lens
        self._passed = passed
        self._confidence = confidence

    async def judge(self, task: str, candidate: str) -> JudgeVote:
        return JudgeVote(lens=self.lens, passed=self._passed, confidence=self._confidence)


class _FakeAdversary:
    def __init__(self, objection: str | None) -> None:
        self._objection = objection

    async def review(self, task: str, answer: str) -> str | None:
        return self._objection


async def test_gate_passes_with_majority():
    gate = VerificationGate([_FakeJudge("a", True), _FakeJudge("b", True), _FakeJudge("c", False)])
    verdict = await gate.verify_answer("task", "answer")
    assert verdict.verdict == "pass"
    assert verdict.confidence > 0


async def test_gate_uncertain_on_split():
    gate = VerificationGate([_FakeJudge("a", True), _FakeJudge("b", False)], pass_threshold=0.6)
    verdict = await gate.verify_answer("task", "answer")
    assert verdict.verdict == "uncertain"


async def test_execution_failure_dominates():
    gate = VerificationGate([_FakeJudge("a", True), _FakeJudge("b", True)])
    verdict = await gate.verify_answer("task", "answer", execution_passed=False)
    assert verdict.verdict == "fail"
    assert verdict.confidence >= 0.9


async def test_low_confidence_pass_becomes_abstention():
    # judges agree (ratio passes) but with weak confidence + no execution oracle →
    # abstain rather than deliver an unsure, ungrounded answer
    gate = VerificationGate([_FakeJudge("a", True, 0.3), _FakeJudge("b", True, 0.3)])
    verdict = await gate.verify_answer("task", "answer")
    assert verdict.verdict == "uncertain"


async def test_execution_pass_dominates_over_judges():
    # Judges would reject, but passing execution (run_checks green) must deliver,
    # not abstain — execution is the oracle in both directions.
    gate = VerificationGate([_FakeJudge("a", False), _FakeJudge("b", False)])
    verdict = await gate.verify_answer("task", "answer", execution_passed=True)
    assert verdict.verdict == "pass"
    assert verdict.confidence >= 0.9


async def test_llm_judge_parses_json_verdict():
    provider = FakeProvider(
        [text_chunks('{"passed": "yes", "confidence": 0.8, "reason": "looks right"}')]
    )
    judge = LLMJudge(provider, "fake", "correctness", "Is it correct?")
    vote = await judge.judge("task", "answer")
    assert vote.passed is True
    assert 0.79 < vote.confidence < 0.81
    assert "right" in vote.rationale


async def test_llm_judge_handles_garbage_as_negative():
    provider = FakeProvider([text_chunks("I cannot produce JSON, sorry.")])
    judge = LLMJudge(provider, "fake", "correctness", "Is it correct?")
    vote = await judge.judge("task", "answer")
    assert vote.passed is False


async def test_adversary_objection_blocks_a_judges_only_pass():
    # judges would pass, but an unrefuted adversarial objection demotes it to uncertain
    gate = VerificationGate(
        [_FakeJudge("a", True), _FakeJudge("b", True)],
        adversary=_FakeAdversary("off-by-one error when the list is empty"),
    )
    verdict = await gate.verify_answer("task", "answer")
    assert verdict.verdict == "uncertain"
    assert any("adversary" in s for s in verdict.signals)
    assert any("off-by-one" in s for s in verdict.signals)  # objection leads the signals


async def test_execution_pass_overrides_adversary_objection():
    # passing tests beat a theoretical objection — execution is the oracle
    gate = VerificationGate([_FakeJudge("a", True)], adversary=_FakeAdversary("could overflow"))
    verdict = await gate.verify_answer("task", "answer", execution_passed=True)
    assert verdict.verdict == "pass"


async def test_sound_adversary_leaves_a_pass_intact():
    gate = VerificationGate(
        [_FakeJudge("a", True), _FakeJudge("b", True)], adversary=_FakeAdversary(None)
    )
    assert (await gate.verify_answer("task", "answer")).verdict == "pass"


async def test_llm_adversary_none_on_sound_else_objection():
    sound = LLMAdversary(FakeProvider([text_chunks("SOUND")]), "fake")
    assert await sound.review("t", "a") is None
    breaker = LLMAdversary(
        FakeProvider([text_chunks("It crashes when the input list is empty.")]), "fake"
    )
    objection = await breaker.review("t", "a")
    assert objection is not None and "empty" in objection


def test_select_by_consensus_picks_largest_cluster():
    # three candidates; two share a behavioral signature
    winner, agreement = select_by_consensus(["A", "B", "C"], key={"A": "x", "B": "x", "C": "y"}.get)
    assert winner in {"A", "B"}
    assert abs(agreement - 2 / 3) < 1e-9
