"""repo_map: compact whole-repo top-level symbol map; skips noise dirs."""

from __future__ import annotations

from pathlib import Path

from lca.core.session import Session
from lca.permissions.approver import AutoApprover
from lca.tools.base import ToolContext
from lca.tools.symbols import RepoMapTool, top_level_symbols


def _ctx(ws: Path) -> ToolContext:
    return ToolContext(
        workspace_root=ws, approver=AutoApprover(), session=Session(workspace_root=ws)
    )


def test_top_level_symbols_python():
    src = (
        "import os\nclass Foo:\n    def method(self):\n        pass\ndef helper():\n    return 1\n"
    )
    syms = top_level_symbols(src, python=True)
    assert syms == ["class Foo", "def helper"]  # nested method excluded


async def test_repo_map_lists_and_skips(tmp_path: Path):
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "a.py").write_text(
        "class Foo:\n    def m(self):\n        pass\ndef helper():\n    return 1\n", "utf-8"
    )
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "x.py").write_text("def should_skip():\n    pass\n", "utf-8")

    content = (await RepoMapTool().run({}, _ctx(tmp_path))).content
    assert "a.py" in content
    assert "class Foo" in content and "def helper" in content
    assert "def m" not in content  # nested, not top-level
    assert "should_skip" not in content  # node_modules skipped
