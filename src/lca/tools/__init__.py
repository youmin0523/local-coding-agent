"""Tools: the capability layer, unified through `ToolRegistry`."""

from __future__ import annotations

from lca.tools.base import (
    Artifact,
    RiskLevel,
    Tool,
    ToolContext,
    ToolResult,
    ToolSpec,
)
from lca.tools.fs_read import read_tools
from lca.tools.fs_write import write_tools
from lca.tools.registry import ToolRegistry
from lca.tools.shell import RunShellTool

__all__ = [
    "Artifact",
    "RiskLevel",
    "RunShellTool",
    "Tool",
    "ToolContext",
    "ToolRegistry",
    "ToolResult",
    "ToolSpec",
    "build_default_registry",
    "read_tools",
    "write_tools",
]


def build_default_registry() -> ToolRegistry:
    """Registry with the built-in filesystem and shell tools (no RAG/web/MCP yet)."""
    registry = ToolRegistry()
    for tool in (*read_tools(), *write_tools(), RunShellTool()):
        registry.register(tool)
    return registry
