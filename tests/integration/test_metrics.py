"""The agent accumulates runtime metrics across turns."""

from __future__ import annotations

from pathlib import Path

from helpers import drain
from lca.core.agent import Agent
from lca.core.session import Session
from lca.permissions.approver import AutoApprover
from lca.permissions.policy import DefaultPolicy
from lca.providers.fake import FakeProvider, text_chunks, tool_chunks
from lca.tools import build_default_registry


async def test_metrics_track_tool_calls_and_turns(workspace: Path):
    (workspace / "hello.txt").write_text("hi", encoding="utf-8")
    provider = FakeProvider(
        [tool_chunks("read_file", {"path": "hello.txt"}, "c1"), text_chunks("it says hi")]
    )
    agent = Agent(
        provider,
        build_default_registry(enable_web=False),
        DefaultPolicy(),
        AutoApprover(),
        model="fake",
    )
    session = Session(workspace_root=workspace)
    await drain(agent.run_turn(session, "read hello.txt"))

    snap = agent.metrics_snapshot()
    assert snap.counters["turns"] == 1
    assert snap.counters["tool_calls"] == 1
    assert snap.counters.get("tool_failures", 0) == 0


async def test_metrics_count_failed_tools(workspace: Path):
    provider = FakeProvider(
        [tool_chunks("read_file", {"path": "missing.txt"}, "c1"), text_chunks("not found")]
    )
    agent = Agent(
        provider,
        build_default_registry(enable_web=False),
        DefaultPolicy(),
        AutoApprover(),
        model="fake",
    )
    await drain(agent.run_turn(Session(workspace_root=workspace), "read missing"))
    snap = agent.metrics_snapshot()
    assert snap.counters["tool_calls"] == 1
    assert snap.counters["tool_failures"] == 1
