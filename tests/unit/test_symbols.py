"""The list_symbols analysis tool."""

from __future__ import annotations

from pathlib import Path

from lca.core.session import Session
from lca.permissions.approver import AutoApprover
from lca.tools.base import ToolContext
from lca.tools.symbols import ListSymbolsTool

PY = """\
import os


class Greeter:
    def __init__(self, name):
        self.name = name

    def greet(self):
        return f"hi {self.name}"


def main():
    Greeter("x").greet()
"""


def _ctx(ws: Path) -> ToolContext:
    return ToolContext(
        workspace_root=ws, approver=AutoApprover(), session=Session(workspace_root=ws)
    )


async def test_python_outline(tmp_path: Path):
    (tmp_path / "g.py").write_text(PY, "utf-8")
    res = await ListSymbolsTool().run({"path": "g.py"}, _ctx(tmp_path))
    assert res.ok
    assert "class Greeter" in res.content
    assert "def greet" in res.content
    assert "def main" in res.content
    assert "L4" in res.content  # class line number


async def test_regex_outline_for_js(tmp_path: Path):
    (tmp_path / "a.js").write_text("export function add(a, b) {\n  return a + b;\n}\n", "utf-8")
    res = await ListSymbolsTool().run({"path": "a.js"}, _ctx(tmp_path))
    assert res.ok
    assert "add" in res.content
