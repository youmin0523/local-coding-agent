"""Eval harness scoring + the metrics collector."""

from __future__ import annotations

from pathlib import Path

from lca.core.agent import Agent
from lca.evaluation.harness import run_eval
from lca.evaluation.models import EvalTask
from lca.observability.metrics import Metrics
from lca.permissions.approver import AutoApprover
from lca.permissions.policy import DefaultPolicy
from lca.providers.fake import FakeProvider, text_chunks
from lca.tools import build_default_registry
from lca.verification.models import Verdict


def _answer_agent(text: str, verifier=None) -> Agent:
    return Agent(
        FakeProvider([text_chunks(text)]),
        build_default_registry(enable_web=False),
        DefaultPolicy(),
        AutoApprover(),
        model="fake",
        verifier=verifier,
    )


class _UncertainVerifier:
    async def verify_answer(
        self, task: str, answer: str, *, execution_passed: bool | None = None
    ) -> Verdict:
        return Verdict(verdict="uncertain", confidence=0.2)


async def test_eval_scores_must_contain(tmp_path: Path):
    tasks = [EvalTask(id="t1", prompt="say hello", must_contain=["hello"])]
    card = await run_eval(lambda: _answer_agent("well, hello there"), tasks, tmp_path)
    assert card.passed == 1
    assert card.pass_rate == 1.0
    assert card.tool_validity == 1.0  # no tools used


async def test_eval_marks_missing_content_as_fail(tmp_path: Path):
    tasks = [EvalTask(id="t1", prompt="say xyzzy", must_contain=["xyzzy"])]
    card = await run_eval(lambda: _answer_agent("nope"), tasks, tmp_path)
    assert card.passed == 0


async def test_eval_rewards_correct_abstention(tmp_path: Path):
    tasks = [EvalTask(id="t1", prompt="guess the secret", expect_abstain=True)]
    card = await run_eval(
        lambda: _answer_agent("the secret is 42", verifier=_UncertainVerifier()), tasks, tmp_path
    )
    assert card.passed == 1
    assert card.results[0].abstained is True


def test_metrics_snapshot():
    m = Metrics()
    m.incr("tool_calls", 3)
    m.incr("tool_calls")
    m.observe("toks_per_s", 10.0)
    m.observe("toks_per_s", 20.0)
    snap = m.snapshot()
    assert snap.counters["tool_calls"] == 4
    assert abs(snap.means["toks_per_s"] - 15.0) < 1e-9
