"""Per-conversation state.

A `Session` holds the message history, the autonomy mode, the token budget (kept
well under the model's nominal max for the 8GB tier), and the per-session
"always allow" cache. It is plain mutable state; the agent loop owns the logic.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from pathlib import Path

from lca.core.messages import Message
from lca.permissions.modes import AutonomyMode


@dataclass
class Session:
    workspace_root: Path
    mode: AutonomyMode = AutonomyMode.GATED
    token_budget: int = 16_384
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    history: list[Message] = field(default_factory=list)
    allow_cache: set[str] = field(default_factory=set)
    tdd: bool = False  # test-first mode: inject the red-green workflow directive

    def add(self, message: Message) -> None:
        self.history.append(message)

    def always_allow(self, tool_name: str) -> None:
        self.allow_cache.add(tool_name)
