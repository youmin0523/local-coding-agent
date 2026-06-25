"""Execution-grounded verification: the turn's run_checks result reaches the verifier
and dominates the verdict (a real failing check can't be argued into a pass)."""

from __future__ import annotations

from pathlib import Path

from helpers import drain, first_of
from lca.core.agent import Agent
from lca.core.session import Session
from lca.permissions.approver import AutoApprover
from lca.permissions.policy import DefaultPolicy
from lca.providers.fake import FakeProvider, text_chunks, tool_chunks
from lca.tools import build_default_registry
from lca.verification.gate import VerificationGate


class _AlwaysPassJudge:
    """An over-eager judge that always says pass — execution should override it."""

    lens = "naive"

    async def judge(self, task: str, candidate: str):
        from lca.verification.models import JudgeVote

        return JudgeVote(lens=self.lens, passed=True, confidence=0.9)


def _agent_with_gate(provider: FakeProvider) -> Agent:
    gate = VerificationGate([_AlwaysPassJudge()])
    return Agent(
        provider,
        build_default_registry(enable_web=False),
        DefaultPolicy(),
        AutoApprover(),
        model="fake",
        verifier=gate,
    )


async def test_failing_checks_force_abstain_despite_eager_judge(tmp_path: Path):
    # The turn runs run_checks on a FAILING test, then answers. Even though the judge
    # always passes, execution=fail must make the gate abstain.
    (tmp_path / "test_bad.py").write_text("def test_x():\n    assert 1 == 2\n", "utf-8")
    provider = FakeProvider(
        [tool_chunks("run_checks", {"kind": "tests"}, "c1"), text_chunks("All good!")]
    )
    agent = _agent_with_gate(provider)
    events = await drain(agent.run_turn(Session(workspace_root=tmp_path), "make the tests pass"))
    verification = first_of(events, "verification")
    assert verification is not None and verification.verdict == "fail"
    assert first_of(events, "abstain") is not None


async def test_passing_checks_confirm_delivery(tmp_path: Path):
    (tmp_path / "test_ok.py").write_text("def test_x():\n    assert 1 == 1\n", "utf-8")
    provider = FakeProvider(
        [tool_chunks("run_checks", {"kind": "tests"}, "c1"), text_chunks("Tests pass.")]
    )
    agent = _agent_with_gate(provider)
    events = await drain(agent.run_turn(Session(workspace_root=tmp_path), "verify the tests"))
    turn = first_of(events, "turn_finished")
    assert turn.stop_reason == "complete"
    assert first_of(events, "verification").verdict == "pass"
