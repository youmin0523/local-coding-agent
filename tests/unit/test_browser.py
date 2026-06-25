"""Browser tools: URL validation + registration (no real browser launched)."""

from __future__ import annotations

from pathlib import Path

import pytest

from lca.core.errors import ToolError
from lca.core.session import Session
from lca.permissions.approver import AutoApprover
from lca.tools import build_default_registry
from lca.tools.base import ToolContext
from lca.tools.browser import BrowserCheckTool, BrowserScreenshotTool


def _ctx(ws: Path) -> ToolContext:
    return ToolContext(
        workspace_root=ws, approver=AutoApprover(), session=Session(workspace_root=ws)
    )


async def test_screenshot_rejects_non_http(tmp_path: Path):
    with pytest.raises(ToolError):
        await BrowserScreenshotTool().run({"url": "file:///etc/passwd"}, _ctx(tmp_path))


async def test_check_rejects_non_http(tmp_path: Path):
    with pytest.raises(ToolError):
        await BrowserCheckTool().run({"url": "ftp://example.com"}, _ctx(tmp_path))


def test_browser_tools_registered():
    reg = build_default_registry(enable_web=False)
    assert "browser_screenshot" in reg
    assert "browser_check" in reg
