"""Agent ↔ memory: recall is injected into context; pass-verdicts are remembered."""

from __future__ import annotations

from pathlib import Path

from helpers import drain
from lca.core.agent import Agent
from lca.core.session import Session
from lca.memory.memory import ExperienceMemory
from lca.memory.store import MemoryStore
from lca.permissions.approver import AutoApprover
from lca.permissions.policy import DefaultPolicy
from lca.providers.fake import FakeProvider, text_chunks
from lca.rag.embedder import HashingEmbedder
from lca.tools import build_default_registry
from lca.verification.models import Verdict


class _PassVerifier:
    async def verify_answer(self, task: str, answer: str) -> Verdict:
        return Verdict(verdict="pass", confidence=0.9)


async def test_recall_injected_into_context(workspace: Path):
    mem = ExperienceMemory(MemoryStore(":memory:"), HashingEmbedder())
    await mem.remember("fix the tax bug", "I divided by the rate; verified by tests", verified=True)

    provider = FakeProvider([text_chunks("done")])
    agent = Agent(
        provider,
        build_default_registry(),
        DefaultPolicy(),
        AutoApprover(),
        model="fake",
        memory=mem,
    )
    await drain(agent.run_turn(Session(workspace_root=workspace), "the tax calculation is wrong"))

    system_prompt = provider.requests[0].messages[0].content or ""
    assert "verified experiences" in system_prompt.lower()
    assert "tax" in system_prompt


async def test_pass_verdict_is_remembered(workspace: Path):
    store = MemoryStore(":memory:")
    mem = ExperienceMemory(store, HashingEmbedder())
    provider = FakeProvider([text_chunks("The fix is to use json.loads.")])
    agent = Agent(
        provider,
        build_default_registry(),
        DefaultPolicy(),
        AutoApprover(),
        model="fake",
        memory=mem,
        verifier=_PassVerifier(),
    )
    await drain(agent.run_turn(Session(workspace_root=workspace), "how do I parse json safely?"))
    assert store.count() == 1
