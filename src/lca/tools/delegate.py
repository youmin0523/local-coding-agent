"""Delegate a focused subtask to a fresh sub-agent.

For a large task, the model can hand a self-contained chunk to a *sub-agent* that
runs with its own clean context (no history baggage), then fold the result back.
This is orchestration, not a new model: the sub-agent shares the same provider,
tools, and workspace. Spawning is bounded to depth 1 (a sub-agent cannot delegate
further) and the spawn itself is a ``WRITE``-risk action, so it is gated like any
other change — the user approves the delegation, and the sub-agent then runs the
subtask autonomously (its file edits are checkpointed and reversible with undo).

The actual sub-agent runner is injected by the agent into ``ToolContext.extra`` so
this tool stays decoupled from the loop (and absent inside a sub-agent → refused).
"""

from __future__ import annotations

from typing import Any

from lca.tools.base import RiskLevel, ToolContext, ToolResult, ToolSpec


class DelegateTool:
    spec = ToolSpec(
        name="delegate",
        description=(
            "Delegate a focused, self-contained subtask to a fresh sub-agent with its own "
            "clean context, and return its result. Use for a chunk of work worth isolating "
            "from this conversation (e.g. 'implement and test the CSV parser in parse.py'). "
            "Give a complete instruction — the sub-agent does not see this chat. It runs the "
            "subtask autonomously in the same workspace; edits are checkpointed (undo works)."
        ),
        parameters={
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "A complete, self-contained instruction for the sub-agent.",
                }
            },
            "required": ["task"],
        },
        risk=RiskLevel.WRITE,
    )

    async def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        task = str(args.get("task", "")).strip()
        if not task:
            return ToolResult.error("delegate requires a non-empty 'task'.")
        runner = ctx.extra.get("subagent")
        if runner is None:
            return ToolResult.error(
                "delegation is not available here (already inside a sub-agent)."
            )
        try:
            stop_reason, answer = await runner(task, ctx.session)
        except Exception as exc:  # a sub-agent must never crash the parent loop
            return ToolResult.error(f"sub-agent failed: {type(exc).__name__}: {exc}")
        if stop_reason != "complete":  # abstain / budget / empty — not a real result
            return ToolResult.error(
                f"sub-agent did not finish the subtask (stopped: {stop_reason}). "
                f"Partial output: {answer or '(none)'}. Try a smaller, clearer subtask."
            )
        return ToolResult.ok_text(
            f"[sub-agent result]\n{answer}" if answer else "[sub-agent produced no answer]"
        )
