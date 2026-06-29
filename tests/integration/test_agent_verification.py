"""The agent's deliver-or-abstain behavior driven by an injected verifier."""

from __future__ import annotations

from pathlib import Path

from helpers import drain, first_of
from lca.core.agent import Agent
from lca.core.session import Session
from lca.permissions.approver import AutoApprover
from lca.permissions.policy import DefaultPolicy
from lca.providers.fake import FakeProvider, text_chunks
from lca.tools import build_default_registry
from lca.verification.models import Verdict


class _StubVerifier:
    def __init__(self, verdict: Verdict) -> None:
        self._verdict = verdict

    async def verify_answer(
        self, task: str, answer: str, *, execution_passed: bool | None = None
    ) -> Verdict:
        return self._verdict


def _agent(verifier) -> Agent:
    provider = FakeProvider([text_chunks("Here is my answer: 42.")])
    return Agent(
        provider,
        build_default_registry(),
        DefaultPolicy(),
        AutoApprover(),
        model="fake",
        verifier=verifier,
    )


class _CrashingVerifier:
    async def verify_answer(
        self, task: str, answer: str, *, execution_passed: bool | None = None
    ) -> Verdict:
        raise RuntimeError("judge unavailable")


async def test_verifier_crash_delivers_but_flags_unverified(workspace: Path):
    # a verifier infra failure must NOT be reported as a confident "pass" — the answer
    # is still delivered (not lost), but flagged uncertain/unverified
    agent = _agent(_CrashingVerifier())
    events = await drain(agent.run_turn(Session(workspace_root=workspace), "q"))
    v = first_of(events, "verification")
    assert v is not None and v.verdict == "uncertain" and v.confidence == 0.0
    assert "42" in first_of(events, "turn_finished").content


async def test_pass_verdict_delivers(workspace: Path):
    agent = _agent(_StubVerifier(Verdict(verdict="pass", confidence=0.9)))
    events = await drain(agent.run_turn(Session(workspace_root=workspace), "what is 6*7?"))
    assert first_of(events, "verification").verdict == "pass"
    turn = first_of(events, "turn_finished")
    assert turn.stop_reason == "complete" and "42" in turn.content
    assert first_of(events, "abstain") is None


async def test_uncertain_verdict_abstains(workspace: Path):
    agent = _agent(
        _StubVerifier(
            Verdict(verdict="uncertain", confidence=0.3, signals=["correctness: concern"])
        )
    )
    events = await drain(agent.run_turn(Session(workspace_root=workspace), "what is 6*7?"))
    assert first_of(events, "abstain") is not None
    assert first_of(events, "turn_finished").stop_reason == "abstained"


class _RepairAwareVerifier:
    """Judges the first draft uncertain, but passes any answer containing 'FIXED'."""

    async def verify_answer(
        self, task: str, answer: str, *, execution_passed: bool | None = None
    ) -> Verdict:
        if "FIXED" in answer:
            return Verdict(verdict="pass", confidence=0.9)
        return Verdict(verdict="uncertain", confidence=0.3, signals=["needs detail"])


async def test_self_repair_recovers_a_judge_uncertain_answer(workspace: Path):
    # the draft is judged uncertain; the self-repair pass yields a passing answer → delivered
    provider = FakeProvider([text_chunks("draft answer"), text_chunks("the FIXED answer")])
    agent = Agent(
        provider,
        build_default_registry(enable_web=False),
        DefaultPolicy(),
        AutoApprover(),
        model="fake",
        verifier=_RepairAwareVerifier(),
    )
    events = await drain(agent.run_turn(Session(workspace_root=workspace), "q"))
    v = first_of(events, "verification")
    assert v.verdict == "pass" and "repair" in v.detail
    tf = first_of(events, "turn_finished")
    assert tf.stop_reason == "complete" and "FIXED" in tf.content
    assert first_of(events, "abstain") is None


async def test_abstains_when_repair_also_fails(workspace: Path):
    # draft uncertain, repaired answer still uncertain → the gate still abstains (bar held)
    provider = FakeProvider([text_chunks("draft"), text_chunks("still weak")])
    agent = Agent(
        provider,
        build_default_registry(enable_web=False),
        DefaultPolicy(),
        AutoApprover(),
        model="fake",
        verifier=_StubVerifier(Verdict(verdict="uncertain", confidence=0.3, signals=["x"])),
    )
    events = await drain(agent.run_turn(Session(workspace_root=workspace), "q"))
    assert first_of(events, "abstain") is not None
    assert first_of(events, "turn_finished").stop_reason == "abstained"


async def test_no_verifier_delivers_normally(workspace: Path):
    agent = _agent(None)
    events = await drain(agent.run_turn(Session(workspace_root=workspace), "hi"))
    assert first_of(events, "verification") is None
    assert first_of(events, "turn_finished").stop_reason == "complete"
