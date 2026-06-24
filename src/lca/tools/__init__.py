"""Tools: the capability layer, unified through `ToolRegistry`."""

from __future__ import annotations

from typing import TYPE_CHECKING

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
from lca.tools.search_code import SearchCodeTool
from lca.tools.shell import RunShellTool

if TYPE_CHECKING:
    from lca.rag.retriever import Retriever

__all__ = [
    "Artifact",
    "RiskLevel",
    "RunShellTool",
    "SearchCodeTool",
    "Tool",
    "ToolContext",
    "ToolRegistry",
    "ToolResult",
    "ToolSpec",
    "build_default_registry",
    "read_tools",
    "write_tools",
]


def build_default_registry(retriever: Retriever | None = None) -> ToolRegistry:
    """Built-in filesystem + shell tools, plus `search_code` if a retriever is given."""
    registry = ToolRegistry()
    for tool in (*read_tools(), *write_tools(), RunShellTool()):
        registry.register(tool)
    if retriever is not None:
        registry.register(SearchCodeTool(retriever))
    return registry
