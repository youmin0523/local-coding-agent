"""The RLVR self-improvement loop: rollouts earn reward, verified data is exported."""

from __future__ import annotations

import json
from pathlib import Path

from lca.core.agent import Agent
from lca.evaluation.models import EvalTask
from lca.learning import export_sft, run_rollouts
from lca.memory.models import MemoryItem
from lca.memory.store import MemoryStore
from lca.permissions.approver import AutoApprover
from lca.permissions.policy import DefaultPolicy
from lca.providers.fake import FakeProvider, text_chunks
from lca.rag.embedder import HashingEmbedder
from lca.tools import build_default_registry
from lca.verification.models import Verdict


class _Verifier:
    def __init__(self, verdict: str) -> None:
        self._verdict = verdict

    async def verify_answer(
        self, task: str, answer: str, *, execution_passed: bool | None = None
    ) -> Verdict:
        return Verdict(verdict=self._verdict, confidence=0.9)


def _agent(verdict: str) -> Agent:
    return Agent(
        FakeProvider([text_chunks("the answer")]),
        build_default_registry(enable_web=False),
        DefaultPolicy(),
        AutoApprover(),
        model="fake",
        verifier=_Verifier(verdict),
    )


async def test_rollouts_count_only_rewarded(tmp_path: Path):
    tasks = [EvalTask(id="a", prompt="do a"), EvalTask(id="b", prompt="do b")]
    rewarded = await run_rollouts(lambda: _agent("pass"), tasks, tmp_path)
    assert rewarded == 2
    rewarded_none = await run_rollouts(lambda: _agent("uncertain"), tasks, tmp_path)
    assert rewarded_none == 0


def test_export_sft_writes_verified_examples(tmp_path: Path):
    store = MemoryStore(":memory:")
    emb = HashingEmbedder()
    for i in range(3):
        item = MemoryItem(kind="episodic", title=f"task {i}", content=f"solution {i}")
        store.add(item, emb.embed([item.title])[0])
    out = tmp_path / "data" / "sft.jsonl"
    n = export_sft(store, out)
    assert n == 3
    lines = out.read_text("utf-8").strip().splitlines()
    assert len(lines) == 3
    first = json.loads(lines[0])
    assert "prompt" in first and "response" in first
