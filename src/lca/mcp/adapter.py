"""Adapt an MCP server tool to lca's `Tool` interface.

An MCP tool, once wrapped, is indistinguishable from a native tool to the agent —
it goes through the same registry, permission gate, and event stream. The MCP
tool's declared input schema becomes the `ToolSpec.parameters`, and its server's
configured risk becomes the `RiskLevel`.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from lca.tools.base import RiskLevel, ToolContext, ToolResult, ToolSpec

# (tool_name, arguments) -> textual result
CallFn = Callable[[str, dict[str, Any]], Awaitable[str]]


class McpToolAdapter:
    def __init__(
        self,
        *,
        name: str,
        description: str,
        schema: dict[str, Any] | None,
        risk: RiskLevel,
        call: CallFn,
    ) -> None:
        self.spec = ToolSpec(
            name=name,
            description=description or f"MCP tool {name}",
            parameters=schema or {"type": "object", "properties": {}},
            risk=risk,
        )
        self._call = call

    async def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        try:
            text = await self._call(self.spec.name, args)
        except Exception as exc:  # surface MCP failures as observations, don't crash
            return ToolResult.error(f"MCP tool '{self.spec.name}' failed: {exc}")
        return ToolResult.ok_text(text)
