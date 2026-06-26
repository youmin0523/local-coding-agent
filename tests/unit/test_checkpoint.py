"""Checkpoint/undo: write tools snapshot before mutating; undo restores/removes."""

from __future__ import annotations

from pathlib import Path

from lca.core.session import Session
from lca.permissions.approver import AutoApprover
from lca.tools.base import ToolContext
from lca.tools.checkpoint import Checkpointer
from lca.tools.fs_write import EditFileTool, WriteFileTool


def _ctx(ws: Path) -> ToolContext:
    return ToolContext(
        workspace_root=ws, approver=AutoApprover(), session=Session(workspace_root=ws)
    )


async def test_undo_restores_overwrite(tmp_path: Path):
    f = tmp_path / "a.txt"
    f.write_text("original", "utf-8")
    await WriteFileTool().run({"path": "a.txt", "content": "changed"}, _ctx(tmp_path))
    assert f.read_text() == "changed"

    assert Checkpointer(tmp_path).undo_last() is not None
    assert f.read_text() == "original"  # restored


async def test_undo_removes_created_file(tmp_path: Path):
    await WriteFileTool().run({"path": "new.txt", "content": "hi"}, _ctx(tmp_path))
    assert (tmp_path / "new.txt").exists()

    Checkpointer(tmp_path).undo_last()
    assert not (tmp_path / "new.txt").exists()  # newly created → removed on undo


async def test_undo_walks_back_multiple_edits(tmp_path: Path):
    f = tmp_path / "b.txt"
    f.write_text("v0", "utf-8")
    await WriteFileTool().run({"path": "b.txt", "content": "v1"}, _ctx(tmp_path))
    await EditFileTool().run(
        {"path": "b.txt", "old_string": "v1", "new_string": "v2"}, _ctx(tmp_path)
    )
    assert f.read_text() == "v2"

    cp = Checkpointer(tmp_path)
    assert cp.pending() == 2
    cp.undo_last()
    assert f.read_text() == "v1"
    cp.undo_last()
    assert f.read_text() == "v0"
    assert cp.pending() == 0
    assert cp.undo_last() is None  # empty
