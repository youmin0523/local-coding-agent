"""End-to-end ReAct loop against the deterministic FakeProvider.

These exercise the whole loop — tool dispatch, the permission gate (allow/ask/deny),
the sandbox path, observation feedback, and the event stream — with zero GPU.
"""

from __future__ import annotations

from pathlib import Path

from helpers import drain, events_of, first_of
from lca.core.agent import Agent
from lca.core.session import Session
from lca.permissions.approver import AutoApprover, DenyingApprover
from lca.permissions.modes import AutonomyMode
from lca.permissions.policy import DefaultPolicy
from lca.providers.fake import FakeProvider, text_chunks, tool_chunks
from lca.tools import build_default_registry


def _agent(provider: FakeProvider, approver) -> Agent:
    return Agent(provider, build_default_registry(), DefaultPolicy(), approver, model="fake")


async def test_delegate_runs_subagent_and_folds_result_back(workspace: Path):
    # parent calls delegate; the sub-agent (turn 2) answers; its result is fed back
    provider = FakeProvider(
        [
            tool_chunks("delegate", {"task": "compute 2+2"}),
            text_chunks("the answer is 4"),
            text_chunks("the sub-agent reported the result"),
        ]
    )
    agent = _agent(provider, AutoApprover())
    session = Session(workspace_root=workspace, mode=AutonomyMode.AUTONOMOUS)
    events = await drain(agent.run_turn(session, "delegate a calculation"))

    finished = events_of(events, "tool_finished")
    delegated = [e for e in finished if e.name == "delegate"]
    assert delegated and delegated[0].result.ok
    assert "the answer is 4" in delegated[0].result.content
    assert first_of(events, "turn_finished").stop_reason == "complete"


async def test_subagent_cannot_delegate_further(workspace: Path):
    # an agent already at depth 1 must not be able to spawn another sub-agent
    provider = FakeProvider(
        [tool_chunks("delegate", {"task": "nested"}), text_chunks("carried on")]
    )
    agent = Agent(
        provider,
        build_default_registry(),
        DefaultPolicy(),
        AutoApprover(),
        model="fake",
        subagent_depth=1,
    )
    session = Session(workspace_root=workspace, mode=AutonomyMode.AUTONOMOUS)
    events = await drain(agent.run_turn(session, "try to delegate from inside"))

    delegated = [e for e in events_of(events, "tool_finished") if e.name == "delegate"]
    assert delegated and delegated[0].result.ok is False
    assert "not available" in delegated[0].result.content


async def test_run_config_is_the_first_event(workspace: Path):
    # routing outcome (model / verify / best-of-N) is surfaced before anything else
    provider = FakeProvider([text_chunks("hi")])
    agent = _agent(provider, AutoApprover())
    events = await drain(agent.run_turn(Session(workspace_root=workspace), "hello"))
    assert events[0].type == "run_config"
    cfg = first_of(events, "run_config")
    assert cfg.model == "fake" and cfg.verify is False and cfg.samples == 1


async def test_files_changed_summarizes_written_paths(workspace: Path):
    provider = FakeProvider(
        [
            tool_chunks("write_file", {"path": "out.py", "content": "x = 1\n"}),
            text_chunks("wrote it"),
        ]
    )
    agent = _agent(provider, AutoApprover())
    events = await drain(agent.run_turn(Session(workspace_root=workspace), "make out.py"))
    fc = first_of(events, "files_changed")
    assert fc is not None and fc.paths == ["out.py"]
    assert (workspace / "out.py").read_text() == "x = 1\n"


async def test_empty_completion_retries_then_answers(workspace: Path):
    # First completion is empty (no text, no tool call); the retry succeeds.
    provider = FakeProvider([text_chunks(""), text_chunks("The answer is 42.")])
    agent = _agent(provider, AutoApprover())
    session = Session(workspace_root=workspace, mode=AutonomyMode.GATED)

    events = await drain(agent.run_turn(session, "what is the answer?"))

    turn = first_of(events, "turn_finished")
    assert turn.stop_reason == "complete" and "42" in turn.content


async def test_empty_completion_gives_up_gracefully(workspace: Path):
    provider = FakeProvider([text_chunks("")] * 3)  # always empty
    agent = _agent(provider, AutoApprover())
    session = Session(workspace_root=workspace, mode=AutonomyMode.GATED)

    turn = first_of(await drain(agent.run_turn(session, "hello?")), "turn_finished")
    assert turn.stop_reason == "empty"


async def test_read_tool_then_answer(workspace: Path):
    (workspace / "hello.txt").write_text("hi there", encoding="utf-8")
    provider = FakeProvider(
        [
            tool_chunks("read_file", {"path": "hello.txt"}, "c1"),
            text_chunks("The file says hi there."),
        ]
    )
    agent = _agent(provider, AutoApprover())
    session = Session(workspace_root=workspace, mode=AutonomyMode.GATED)

    events = await drain(agent.run_turn(session, "what is in hello.txt?"))

    proposed = first_of(events, "tool_proposed")
    assert proposed is not None and proposed.call.name == "read_file"
    # READ risk → no approval prompt
    assert not events_of(events, "approval_required")
    finished = first_of(events, "tool_finished")
    assert finished is not None and "hi there" in finished.result.content
    turn = first_of(events, "turn_finished")
    assert turn.stop_reason == "complete"
    assert "The file says" in turn.content
    # the model's second call saw the tool result fed back
    assert any(m.role == "tool" for m in provider.requests[1].messages)


async def test_write_denied_in_gated_mode(workspace: Path):
    provider = FakeProvider(
        [
            tool_chunks("write_file", {"path": "x.txt", "content": "data"}, "c1"),
            text_chunks("Understood, I will not write it."),
        ]
    )
    agent = _agent(provider, DenyingApprover())
    session = Session(workspace_root=workspace, mode=AutonomyMode.GATED)

    events = await drain(agent.run_turn(session, "create x.txt"))

    approval = first_of(events, "approval_required")
    assert approval is not None and approval.call.name == "write_file"
    resolved = first_of(events, "approval_resolved")
    assert resolved is not None and resolved.approved is False
    assert not (workspace / "x.txt").exists()  # write was blocked
    assert first_of(events, "turn_finished").stop_reason == "complete"


async def test_write_allowed_in_autonomous_mode(workspace: Path):
    provider = FakeProvider(
        [
            tool_chunks("write_file", {"path": "x.txt", "content": "data"}, "c1"),
            text_chunks("Done."),
        ]
    )
    agent = _agent(provider, AutoApprover())
    session = Session(workspace_root=workspace, mode=AutonomyMode.AUTONOMOUS)

    events = await drain(agent.run_turn(session, "create x.txt"))

    # autonomous mode auto-allows WRITE (≤ ceiling) → no prompt
    assert not events_of(events, "approval_required")
    assert (workspace / "x.txt").read_text() == "data"


async def test_unknown_tool_is_recoverable(workspace: Path):
    provider = FakeProvider(
        [
            tool_chunks("does_not_exist", {}, "c1"),
            text_chunks("Let me answer directly: 42."),
        ]
    )
    agent = _agent(provider, AutoApprover())
    session = Session(workspace_root=workspace, mode=AutonomyMode.GATED)

    events = await drain(agent.run_turn(session, "use a missing tool"))

    assert not events_of(events, "tool_started")  # never started an unknown tool
    turn = first_of(events, "turn_finished")
    assert turn.stop_reason == "complete" and "42" in turn.content


async def test_iteration_budget_stops_loops(workspace: Path):
    # The model keeps calling a tool forever; the loop must stop at the cap.
    (workspace / "f.txt").write_text("x", encoding="utf-8")

    def always_read(_req):
        return tool_chunks("read_file", {"path": "f.txt"}, "c1")

    provider = FakeProvider(always_read)
    agent = Agent(
        provider,
        build_default_registry(),
        DefaultPolicy(),
        AutoApprover(),
        model="fake",
        max_tool_iterations=3,
    )
    session = Session(workspace_root=workspace)

    events = await drain(agent.run_turn(session, "loop forever"))
    turn = first_of(events, "turn_finished")
    assert turn.stop_reason == "budget"
