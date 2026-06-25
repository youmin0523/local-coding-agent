"""MCP client: the agent connects to stdio MCP servers and exposes their tools
through the same `ToolRegistry` as native tools."""

from lca.mcp.adapter import McpToolAdapter
from lca.mcp.client import MCPClientManager, McpSession, McpToolInfo
from lca.mcp.servers import ServerSpec, default_servers

__all__ = [
    "MCPClientManager",
    "McpSession",
    "McpToolAdapter",
    "McpToolInfo",
    "ServerSpec",
    "default_servers",
]
