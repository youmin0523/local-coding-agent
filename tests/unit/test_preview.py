"""preview_call: a reviewable diff/command for a gated tool call."""

from __future__ import annotations

from pathlib import Path

from lca.core.messages import ToolCall
from lca.tools.preview import preview_call


def test_write_file_preview_is_a_diff(tmp_path: Path):
    (tmp_path / "a.py").write_text("x = 1\n", "utf-8")
    call = ToolCall(id="1", name="write_file", arguments={"path": "a.py", "content": "x = 2\n"})
    out = preview_call(call, tmp_path)
    assert "-x = 1" in out and "+x = 2" in out


def test_new_file_preview(tmp_path: Path):
    # new file with content → shown as added lines; empty new file → "(new file)" label
    call = ToolCall(id="1", name="write_file", arguments={"path": "n.py", "content": "y = 1\n"})
    assert "+y = 1" in preview_call(call, tmp_path)
    empty = ToolCall(id="2", name="write_file", arguments={"path": "e.py", "content": ""})
    assert "new file" in preview_call(empty, tmp_path)


def test_edit_and_shell_preview(tmp_path: Path):
    edit = ToolCall(id="1", name="edit_file", arguments={"old_string": "a", "new_string": "b"})
    assert "- a" in preview_call(edit, tmp_path) and "+ b" in preview_call(edit, tmp_path)
    sh = ToolCall(id="2", name="run_shell", arguments={"command": "ls -la"})
    assert "ls -la" in preview_call(sh, tmp_path)


def test_no_preview_for_read_tools(tmp_path: Path):
    call = ToolCall(id="1", name="read_file", arguments={"path": "x"})
    assert preview_call(call, tmp_path) == ""
