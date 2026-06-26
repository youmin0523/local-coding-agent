"""`update_plan` — a lightweight TODO plan the agent maintains for multi-step work.

Mirrors Claude Code's TodoWrite: the agent passes the FULL step list each time
(marking each pending/in_progress/done); the tool renders a checklist that the CLI
and web UI surface, so multi-step tasks stay organized and visible. Read-only.
"""

from __future__ import annotations

from typing import Any

from lca.tools.base import RiskLevel, ToolContext, ToolResult, ToolSpec

_ICON = {"done": "✔", "completed": "✔", "in_progress": "▶", "pending": "○"}


class UpdatePlanTool:
    spec = ToolSpec(
        name="update_plan",
        description=(
            "Record or update a short TODO plan for a multi-step task. Pass the FULL "
            "ordered list each call; set each step's status to pending, in_progress, or "
            "done. Use it for non-trivial multi-step work to stay organized and visible."
        ),
        parameters={
            "type": "object",
            "properties": {
                "steps": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "step": {"type": "string", "description": "What this step does."},
                            "status": {"enum": ["pending", "in_progress", "done"]},
                        },
                        "required": ["step", "status"],
                    },
                }
            },
            "required": ["steps"],
        },
        risk=RiskLevel.READ,
    )

    async def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        raw = args.get("steps") or []
        if not isinstance(raw, list) or not raw:
            return ToolResult.error("steps must be a non-empty list of {step, status}.")
        lines: list[str] = ["Plan:"]
        done = 0
        for item in raw:
            if not isinstance(item, dict):
                continue
            status = str(item.get("status", "pending")).lower()
            step = str(item.get("step", "")).strip()
            if not step:
                continue
            if status in ("done", "completed"):
                done += 1
            lines.append(f"  {_ICON.get(status, '•')} {step}")
        total = len(lines) - 1
        lines.append(f"  ({done}/{total} done)")
        return ToolResult.ok_text("\n".join(lines))
