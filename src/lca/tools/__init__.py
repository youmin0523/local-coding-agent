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
from lca.tools.code_exec import RunPythonTool
from lca.tools.fs_read import read_tools
from lca.tools.fs_write import write_tools
from lca.tools.registry import ToolRegistry
from lca.tools.run_checks import RunChecksTool
from lca.tools.search_code import SearchCodeTool
from lca.tools.shell import RunShellTool
from lca.tools.web.fetch import FetchUrlTool
from lca.tools.web.search import WebSearchTool

if TYPE_CHECKING:
    from lca.rag.retriever import Retriever

__all__ = [
    "Artifact",
    "FetchUrlTool",
    "RiskLevel",
    "RunChecksTool",
    "RunPythonTool",
    "RunShellTool",
    "SearchCodeTool",
    "Tool",
    "ToolContext",
    "ToolRegistry",
    "ToolResult",
    "ToolSpec",
    "WebSearchTool",
    "build_default_registry",
    "read_tools",
    "write_tools",
]


def build_default_registry(
    retriever: Retriever | None = None, *, enable_web: bool = True
) -> ToolRegistry:
    """Built-in tools: filesystem, shell, execution, checks; web + search_code optional."""
    registry = ToolRegistry()
    builtins: list[Tool] = [
        *read_tools(),
        *write_tools(),
        RunShellTool(),
        RunPythonTool(),
        RunChecksTool(),
    ]
    if enable_web:
        builtins.extend([WebSearchTool(), FetchUrlTool()])
    for tool in builtins:
        registry.register(tool)
    if retriever is not None:
        registry.register(SearchCodeTool(retriever))
    return registry
