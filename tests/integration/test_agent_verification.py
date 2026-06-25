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


async def test_no_verifier_delivers_normally(workspace: Path):
    agent = _agent(None)
    events = await drain(agent.run_turn(Session(workspace_root=workspace), "hi"))
    assert first_of(events, "verification") is None
    assert first_of(events, "turn_finished").stop_reason == "complete"
