"""Adversarial tests for the safety boundaries (model output is untrusted).

Covers workspace path confinement and the shell allowlist — the two places where
malicious or mistaken model output could otherwise touch the host.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from lca.core.errors import ToolError
from lca.core.session import Session
from lca.permissions.approver import AutoApprover
from lca.tools.base import ToolContext
from lca.tools.fs_read import ReadFileTool
from lca.tools.shell import RunShellTool
from lca.tools.util import safe_resolve


def _ctx(ws: Path, sandbox=None) -> ToolContext:
    return ToolContext(
        workspace_root=ws,
        approver=AutoApprover(),
        session=Session(workspace_root=ws),
        sandbox=sandbox,
    )


@pytest.mark.parametrize(
    "escape",
    ["../secret.txt", "../../etc/passwd", "a/../../escape", "sub/../../../out", "C:\\Windows\\x"],
)
def test_path_escapes_are_blocked(tmp_path: Path, escape: str):
    with pytest.raises(ToolError):
        safe_resolve(tmp_path, escape)


def test_legitimate_paths_resolve(tmp_path: Path):
    assert safe_resolve(tmp_path, "a/b.txt").parent.name == "a"
    assert safe_resolve(tmp_path, "./x").name == "x"


async def test_read_file_cannot_escape_workspace(tmp_path: Path):
    with pytest.raises(ToolError):
        await ReadFileTool().run({"path": "../../../etc/hosts"}, _ctx(tmp_path))


async def test_shell_rejects_non_allowlisted(tmp_path: Path):
    tool = RunShellTool()
    for cmd in ["rm -rf /", "curl http://evil", "bash -c whoami", "powershell -c x", "python; rm"]:
        res = await tool.run({"command": cmd}, _ctx(tmp_path))
        assert not res.ok
        assert "allowlist" in res.content


async def test_shell_allows_listed_executable_passes_gate(tmp_path: Path):
    # "git" is allowlisted: it gets past the allowlist check (then needs a sandbox).
    res = await RunShellTool().run({"command": "git status"}, _ctx(tmp_path, sandbox=None))
    assert not res.ok
    assert "allowlist" not in res.content  # rejected for lack of sandbox, NOT the allowlist
