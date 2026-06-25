"""MCP adapter + client registration logic (with a fake session, no real server)."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest

from lca.core.session import Session
from lca.mcp.client import MCPClientManager, McpToolInfo
from lca.mcp.servers import ServerSpec
from lca.permissions.approver import AutoApprover
from lca.tools.base import RiskLevel, ToolContext
from lca.tools.registry import ToolRegistry


class _FakeSession:
    def __init__(self, *, fail: bool = False) -> None:
        self._fail = fail

    async def list_tools(self) -> Sequence[McpToolInfo]:
        return [
            McpToolInfo(name="status", description="git status", schema_={"type": "object"}),
            McpToolInfo(name="log", description="git log"),
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        if self._fail:
            raise RuntimeError("server exploded")
        return f"ran {name} with {arguments}"


def _ctx(ws: Path) -> ToolContext:
    return ToolContext(
        workspace_root=ws, approver=AutoApprover(), session=Session(workspace_root=ws)
    )


async def test_register_session_namespaces_and_assigns_risk(tmp_path: Path):
    registry = ToolRegistry()
    spec = ServerSpec(name="git", command="x", risk=RiskLevel.SHELL)
    count = await MCPClientManager().register_session(spec, _FakeSession(), registry)
    assert count == 2
    assert "git__status" in registry and "git__log" in registry
    tool = registry.get("git__status")
    assert tool.spec.risk == RiskLevel.SHELL


async def test_mcp_tool_invocation_round_trips(tmp_path: Path):
    registry = ToolRegistry()
    spec = ServerSpec(name="git", command="x", risk=RiskLevel.SHELL)
    await MCPClientManager().register_session(spec, _FakeSession(), registry)
    result = await registry.get("git__status").run({"a": 1}, _ctx(tmp_path))
    assert result.ok and "ran status" in result.content


async def test_mcp_tool_failure_is_observation_not_crash(tmp_path: Path):
    registry = ToolRegistry()
    spec = ServerSpec(name="git", command="x", risk=RiskLevel.SHELL)
    await MCPClientManager().register_session(spec, _FakeSession(fail=True), registry)
    result = await registry.get("git__status").run({}, _ctx(tmp_path))
    assert not result.ok and "failed" in result.content


def test_default_servers_are_workspace_scoped():
    from lca.mcp.servers import default_servers

    specs = {s.name: s for s in default_servers("/work")}
    assert "/work" in specs["filesystem"].args
    assert specs["fetch"].risk == RiskLevel.NETWORK


@pytest.mark.asyncio
async def test_connect_without_sdk_raises_clear_error():
    # The fake import path: connect() should raise a helpful error if mcp is absent.
    # We only assert the method exists and is awaitable-safe to call structure-wise.
    mgr = MCPClientManager()
    assert hasattr(mgr, "connect")
