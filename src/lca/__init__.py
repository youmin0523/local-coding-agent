"""lca — a 100% local, free, verification-grounded coding agent.

The package is organized in strict layers (enforced by import-linter):

    cli / web            UI adapters (Typer+Rich, FastAPI+SSE)
        |
    core                 the UI-agnostic agent: ReAct loop, session, events
        |
    providers, tools,    swappable engines, the tool registry, RAG, memory,
    rag, memory,         multi-pass verification, difficulty routing, MCP,
    verification,        the permission/safety layer
    routing, mcp,
    permissions
        |
    config, observability   settings, paths, structured logging

Nothing below `core` may import `cli` or `web`; that is what keeps the agent
core consumable identically by the terminal and the browser.
"""

__version__ = "0.1.0"
