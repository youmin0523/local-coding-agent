"""Best-of-N: with samples>1 the agent verifies several candidates and delivers
the best-verified one (or abstains if none verify)."""

from __future__ import annotations

from pathlib import Path

from helpers import drain, first_of
from lca.core.agent import Agent
from lca.core.session import Session
from lca.permissions.approver import AutoApprover
from lca.permissions.policy import DefaultPolicy
from lca.providers.base import ChatChunk, ChatRequest
from lca.providers.fake import FakeProvider, text_chunks
from lca.tools import build_default_registry
from lca.verification.models import Verdict


def _candidate_provider(answers: list[str]) -> FakeProvider:
    """A provider that returns a different answer on each call (no tools)."""
    calls = {"n": 0}

    def script(_req: ChatRequest) -> list[ChatChunk]:
        i = min(calls["n"], len(answers) - 1)
        calls["n"] += 1
        return text_chunks(answers[i])

    return FakeProvider(script)


class _KeywordVerifier:
    """Passes only candidates containing the magic word; confidence = length-based."""

    def __init__(self, magic: str) -> None:
        self._magic = magic

    async def verify_answer(self, task: str, answer: str) -> Verdict:
        if self._magic in answer:
            return Verdict(verdict="pass", confidence=0.5 + 0.01 * len(answer))
        return Verdict(verdict="uncertain", confidence=0.2, signals=["missing magic word"])


def _agent(provider: FakeProvider, verifier, samples: int) -> Agent:
    return Agent(
        provider,
        build_default_registry(enable_web=False),
        DefaultPolicy(),
        AutoApprover(),
        model="fake",
        verifier=verifier,
        samples=samples,
    )


async def test_best_of_n_picks_a_passing_candidate(workspace: Path):
    # First answer fails verification; a later sampled candidate passes.
    provider = _candidate_provider(["totally wrong", "this one has MAGIC inside"])
    agent = _agent(provider, _KeywordVerifier("MAGIC"), samples=2)
    events = await drain(agent.run_turn(Session(workspace_root=workspace), "do the thing"))
    assert first_of(events, "verification").verdict == "pass"
    turn = first_of(events, "turn_finished")
    assert turn.stop_reason == "complete" and "MAGIC" in turn.content
    assert first_of(events, "abstain") is None


async def test_best_of_n_abstains_when_none_pass(workspace: Path):
    provider = _candidate_provider(["nope", "still nope", "nah"])
    agent = _agent(provider, _KeywordVerifier("MAGIC"), samples=3)
    events = await drain(agent.run_turn(Session(workspace_root=workspace), "do the thing"))
    assert first_of(events, "abstain") is not None
    assert first_of(events, "turn_finished").stop_reason == "abstained"
