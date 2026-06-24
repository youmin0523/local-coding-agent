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

if TYPE_CHECKING:
    from lca.rag.retriever import Retriever

__all__ = [
    "Artifact",
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
    "build_default_registry",
    "read_tools",
    "write_tools",
]


def build_default_registry(retriever: Retriever | None = None) -> ToolRegistry:
    """Built-in filesystem, shell, execution, and check tools; `search_code` if a retriever."""
    registry = ToolRegistry()
    builtins: list[Tool] = [
        *read_tools(),
        *write_tools(),
        RunShellTool(),
        RunPythonTool(),
        RunChecksTool(),
    ]
    for tool in builtins:
        registry.register(tool)
    if retriever is not None:
        registry.register(SearchCodeTool(retriever))
    return registry
