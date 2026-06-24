"""The unified tool registry.

Native tools and (later) MCP tools are registered here and presented to the model
as one homogeneous list. MCP tools are namespaced ``{server}__{tool}`` to avoid
collisions; native tool names win on an exact clash.

The registry exposes `ToolSpec`s (with the *exposed* name) for building both the
engine's tool list and the GBNF grammar, and resolves an exposed name back to the
concrete `Tool` for execution.
"""

from __future__ import annotations

from lca.core.errors import ToolNotFoundError
from lca.observability.logging import get_logger
from lca.tools.base import Tool, ToolSpec

log = get_logger("tools.registry")


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}
        self._exposed_spec: dict[str, ToolSpec] = {}

    def register(self, tool: Tool, *, replace: bool = False) -> None:
        """Register a native tool under its own name."""
        self._add(tool.spec.name, tool, replace=replace)

    def register_mcp(self, server: str, tool: Tool, *, replace: bool = True) -> None:
        """Register an MCP tool under a namespaced name (``server__tool``)."""
        exposed = f"{server}__{tool.spec.name}"
        if exposed in self._tools and not replace:
            raise ValueError(f"tool {exposed!r} already registered")
        self._add(exposed, tool, replace=True)

    def _add(self, exposed: str, tool: Tool, *, replace: bool) -> None:
        if exposed in self._tools and not replace:
            raise ValueError(f"tool {exposed!r} already registered")
        self._tools[exposed] = tool
        self._exposed_spec[exposed] = tool.spec.model_copy(update={"name": exposed})

    def get(self, name: str) -> Tool:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise ToolNotFoundError(name) from exc

    def specs(self) -> list[ToolSpec]:
        """Specs with their *exposed* names — what the model and grammar see."""
        return list(self._exposed_spec.values())

    def names(self) -> list[str]:
        return list(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    def __len__(self) -> int:
        return len(self._tools)
