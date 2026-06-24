"""Filesystem tools and workspace path confinement."""

from __future__ import annotations

from pathlib import Path

import pytest

from lca.core.errors import ToolError
from lca.core.session import Session
from lca.permissions.approver import AutoApprover
from lca.tools.base import ToolContext
from lca.tools.fs_read import ReadFileTool
from lca.tools.fs_write import EditFileTool, WriteFileTool
from lca.tools.util import safe_resolve


def _ctx(ws: Path) -> ToolContext:
    return ToolContext(
        workspace_root=ws, approver=AutoApprover(), session=Session(workspace_root=ws)
    )


def test_safe_resolve_blocks_escape(tmp_path: Path):
    with pytest.raises(ToolError):
        safe_resolve(tmp_path, "../secret.txt")


async def test_write_then_read_roundtrip(tmp_path: Path):
    ctx = _ctx(tmp_path)
    res = await WriteFileTool().run({"path": "a/b.txt", "content": "hello"}, ctx)
    assert res.ok
    assert (tmp_path / "a" / "b.txt").read_text() == "hello"
    assert any(a.kind == "diff" for a in res.artifacts)

    read = await ReadFileTool().run({"path": "a/b.txt"}, ctx)
    assert "hello" in read.content


async def test_edit_requires_unique_match(tmp_path: Path):
    ctx = _ctx(tmp_path)
    (tmp_path / "f.py").write_text("x = 1\nx = 1\n")
    res = await EditFileTool().run(
        {"path": "f.py", "old_string": "x = 1", "new_string": "x = 2"}, ctx
    )
    assert not res.ok  # not unique
    (tmp_path / "g.py").write_text("value = 1\n")
    ok = await EditFileTool().run(
        {"path": "g.py", "old_string": "value = 1", "new_string": "value = 2"}, ctx
    )
    assert ok.ok
    assert (tmp_path / "g.py").read_text() == "value = 2\n"


async def test_edit_missing_string_errors(tmp_path: Path):
    ctx = _ctx(tmp_path)
    (tmp_path / "f.py").write_text("hello\n")
    res = await EditFileTool().run({"path": "f.py", "old_string": "absent", "new_string": "x"}, ctx)
    assert not res.ok


async def test_read_file_path_escape_raises(tmp_path: Path):
    ctx = _ctx(tmp_path)
    with pytest.raises(ToolError):
        await ReadFileTool().run({"path": "../../etc/hosts"}, ctx)
