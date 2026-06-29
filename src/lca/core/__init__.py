"""The UI-agnostic agent core: messages, events, the ReAct loop, session state.

Re-exports are **lazy** (PEP 562 ``__getattr__``): eagerly importing ``agent`` here
created a package init-order cycle (``providers.base`` → ``core.messages`` → this
``__init__`` → ``core.agent`` → ``providers.base`` partially initialized), which broke
``import lca.providers.registry`` before anything had imported ``lca.core``. Importing
submodules (``from lca.core.agent import Agent``) is unaffected and is what the codebase
actually uses; ``from lca.core import Agent`` still works, resolved on first access.
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from lca.core.agent import Agent
    from lca.core.context import ContextBuilder, RetrievedContext
    from lca.core.events import AgentEvent
    from lca.core.messages import Message, Role, ToolCall
    from lca.core.session import Session

__all__ = [
    "Agent",
    "AgentEvent",
    "ContextBuilder",
    "Message",
    "RetrievedContext",
    "Role",
    "Session",
    "ToolCall",
]

_LAZY = {
    "Agent": "lca.core.agent",
    "ContextBuilder": "lca.core.context",
    "RetrievedContext": "lca.core.context",
    "AgentEvent": "lca.core.events",
    "Message": "lca.core.messages",
    "Role": "lca.core.messages",
    "ToolCall": "lca.core.messages",
    "Session": "lca.core.session",
}


def __getattr__(name: str) -> Any:
    target = _LAZY.get(name)
    if target is None:
        raise AttributeError(f"module 'lca.core' has no attribute {name!r}")
    return getattr(importlib.import_module(target), name)
