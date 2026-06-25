"""Declarative MCP server configuration.

Each server is a stdio subprocess. Risk is assigned per server (so the permission
gate treats, say, a filesystem-write server as WRITE and a fetch server as
NETWORK). The defaults are the well-known reference servers; they require ``npx``
(Node) or ``uvx`` (uv) and a first-run download.
"""

from __future__ import annotations

from pydantic import BaseModel

from lca.tools.base import RiskLevel


class ServerSpec(BaseModel):
    name: str
    command: str
    args: list[str] = []
    risk: RiskLevel = RiskLevel.NETWORK
    enabled: bool = True


def default_servers(workspace: str) -> list[ServerSpec]:
    """Reference local MCP servers scoped to the workspace."""
    return [
        ServerSpec(
            name="filesystem",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-filesystem", workspace],
            risk=RiskLevel.WRITE,
        ),
        ServerSpec(
            name="git",
            command="uvx",
            args=["mcp-server-git", "--repository", workspace],
            risk=RiskLevel.SHELL,
        ),
        ServerSpec(
            name="fetch",
            command="uvx",
            args=["mcp-server-fetch"],
            risk=RiskLevel.NETWORK,
        ),
    ]
