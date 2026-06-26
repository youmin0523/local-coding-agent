"""update_plan: renders a status checklist; rejects empty input."""

from __future__ import annotations

from pathlib import Path

from lca.core.session import Session
from lca.permissions.approver import AutoApprover
from lca.tools.base import ToolContext
from lca.tools.plan import UpdatePlanTool


def _ctx(ws: Path) -> ToolContext:
    return ToolContext(
        workspace_root=ws, approver=AutoApprover(), session=Session(workspace_root=ws)
    )


async def test_plan_renders_checklist(tmp_path: Path):
    res = await UpdatePlanTool().run(
        {
            "steps": [
                {"step": "read the file", "status": "done"},
                {"step": "write the fix", "status": "in_progress"},
                {"step": "run tests", "status": "pending"},
            ]
        },
        _ctx(tmp_path),
    )
    assert res.ok
    assert "✔ read the file" in res.content
    assert "▶ write the fix" in res.content
    assert "○ run tests" in res.content
    assert "(1/3 done)" in res.content


async def test_plan_rejects_empty(tmp_path: Path):
    res = await UpdatePlanTool().run({"steps": []}, _ctx(tmp_path))
    assert not res.ok


def test_plan_tool_registered():
    from lca.tools import build_default_registry

    assert "update_plan" in build_default_registry(enable_web=False)
