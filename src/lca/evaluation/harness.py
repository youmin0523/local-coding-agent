"""Run a set of eval tasks through the agent and score the results.

Produces the portfolio numbers: pass rate, tool-call validity, and whether the
agent correctly *abstained* where it should. Engine-agnostic — pass any
agent factory (real engine for `lca eval`, FakeProvider in tests).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from lca.core.agent import Agent
from lca.core.session import Session
from lca.evaluation.models import EvalTask, Scorecard, TaskResult

AgentFactory = Callable[[], Agent]


async def run_eval(factory: AgentFactory, tasks: list[EvalTask], workspace: Path) -> Scorecard:
    results: list[TaskResult] = []
    total_calls = 0
    total_failures = 0

    for task in tasks:
        agent = factory()
        session = Session(workspace_root=workspace)
        answer = ""
        abstained = False
        calls = 0
        failures = 0
        async for event in agent.run_turn(session, task.prompt):
            kind = event.type
            if kind == "tool_finished":
                calls += 1
                if not event.result.ok:  # type: ignore[union-attr]
                    failures += 1
            elif kind == "abstain":
                abstained = True
            elif kind == "turn_finished":
                answer = event.content  # type: ignore[union-attr]

        total_calls += calls
        total_failures += failures
        passed = _passed(task, answer, abstained)
        results.append(
            TaskResult(
                id=task.id,
                passed=passed,
                abstained=abstained,
                tool_calls=calls,
                tool_failures=failures,
                detail="" if passed else f"answer did not satisfy task ({len(answer)} chars)",
            )
        )

    return Scorecard(
        total=len(tasks),
        passed=sum(1 for r in results if r.passed),
        tool_calls=total_calls,
        tool_failures=total_failures,
        results=results,
    )


def _passed(task: EvalTask, answer: str, abstained: bool) -> bool:
    if task.expect_abstain:
        return abstained
    if abstained:
        return False
    return all(needle.lower() in answer.lower() for needle in task.must_contain)
