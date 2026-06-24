"""Tool registry: registration, lookup, MCP namespacing, collisions."""

from __future__ import annotations

import pytest

from lca.core.errors import ToolNotFoundError
from lca.tools import build_default_registry
from lca.tools.base import RiskLevel, ToolResult, ToolSpec
from lca.tools.registry import ToolRegistry


class _Dummy:
    def __init__(self, name: str) -> None:
        self.spec = ToolSpec(name=name, description="d", risk=RiskLevel.READ)

    async def run(self, args, ctx):  # pragma: no cover - not executed here
        return ToolResult.ok_text("ok")


def test_default_registry_has_builtin_tools():
    reg = build_default_registry()
    names = set(reg.names())
    assert {
        "read_file",
        "write_file",
        "edit_file",
        "run_shell",
        "glob",
        "grep",
        "list_dir",
    } <= names


def test_get_unknown_raises():
    reg = ToolRegistry()
    with pytest.raises(ToolNotFoundError):
        reg.get("nope")


def test_duplicate_native_registration_raises():
    reg = ToolRegistry()
    reg.register(_Dummy("a"))
    with pytest.raises(ValueError):
        reg.register(_Dummy("a"))


def test_mcp_tools_are_namespaced():
    reg = ToolRegistry()
    reg.register_mcp("git", _Dummy("status"))
    assert "git__status" in reg
    spec = next(s for s in reg.specs() if s.name == "git__status")
    assert spec.name == "git__status"
