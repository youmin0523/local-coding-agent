"""MCP client manager.

The agent acts as an MCP *client*: it launches configured stdio servers, lists
their tools, and registers each into the shared `ToolRegistry` (namespaced
``server__tool``). The registration/adaptation logic is decoupled from the SDK via
the small `McpSession` Protocol, so it is unit-tested with a fake session; the real
stdio connector (official ``mcp`` SDK) is a thin, lazily-imported layer.
"""

from __future__ import annotations

import contextlib
from collections.abc import Sequence
from typing import Any, Protocol

from pydantic import BaseModel

from lca.mcp.adapter import McpToolAdapter
from lca.mcp.servers import ServerSpec
from lca.observability.logging import get_logger
from lca.tools.registry import ToolRegistry

log = get_logger("mcp.client")


class McpToolInfo(BaseModel):
    name: str
    description: str = ""
    schema_: dict[str, Any] = {}


class McpSession(Protocol):
    async def list_tools(self) -> Sequence[McpToolInfo]: ...
    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str: ...


class MCPClientManager:
    def __init__(self) -> None:
        self._stack = contextlib.AsyncExitStack()
        self._sessions: dict[str, McpSession] = {}

    async def register_session(
        self, spec: ServerSpec, session: McpSession, registry: ToolRegistry
    ) -> int:
        """Register all of a session's tools into the registry. Returns the count."""
        infos = await session.list_tools()
        for info in infos:
            registry.register_mcp(
                spec.name,
                McpToolAdapter(
                    name=info.name,
                    description=info.description,
                    schema=info.schema_,
                    risk=spec.risk,
                    call=session.call_tool,
                ),
            )
        self._sessions[spec.name] = session
        log.info("mcp.registered", server=spec.name, tools=len(infos))
        return len(infos)

    async def connect(self, spec: ServerSpec) -> McpSession:
        """Launch a stdio MCP server and return a session (real SDK path)."""
        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client
        except ImportError as exc:  # pragma: no cover - requires the `mcp` extra
            raise RuntimeError("MCP support requires `uv sync --extra mcp`") from exc

        params = StdioServerParameters(command=spec.command, args=spec.args)
        read, write = await self._stack.enter_async_context(stdio_client(params))
        session = await self._stack.enter_async_context(ClientSession(read, write))
        await session.initialize()
        return _SdkSession(session)

    async def connect_all(self, specs: list[ServerSpec], registry: ToolRegistry) -> int:
        total = 0
        for spec in specs:
            if not spec.enabled:
                continue
            try:
                session = await self.connect(spec)
                total += await self.register_session(spec, session, registry)
            except Exception as exc:  # a broken server must not stop the others
                log.warning("mcp.connect_failed", server=spec.name, error=str(exc))
        return total

    async def aclose(self) -> None:
        await self._stack.aclose()
        self._sessions.clear()


class _SdkSession:  # pragma: no cover - thin wrapper over the mcp SDK
    """Maps the official mcp SDK session onto our `McpSession` Protocol."""

    def __init__(self, session: Any) -> None:
        self._session = session

    async def list_tools(self) -> Sequence[McpToolInfo]:
        result = await self._session.list_tools()
        return [
            McpToolInfo(
                name=t.name,
                description=getattr(t, "description", "") or "",
                schema_=getattr(t, "inputSchema", {}) or {},
            )
            for t in result.tools
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        result = await self._session.call_tool(name, arguments)
        parts: list[str] = []
        for block in getattr(result, "content", []) or []:
            text = getattr(block, "text", None)
            if text:
                parts.append(text)
        return "\n".join(parts) if parts else "(no content)"
