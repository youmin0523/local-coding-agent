"""The permission policy: decides allow / deny / ask for a tool call.

The matrix is intentionally simple and auditable:

| risk \\ mode | GATED | AUTONOMOUS (≤ ceiling) | PLAN |
|--------------|-------|------------------------|------|
| READ         | allow | allow                  | allow|
| WRITE        | ask   | allow                  | deny |
| SHELL        | ask   | allow                  | deny |
| NETWORK      | ask   | allow (if ≤ ceiling)   | deny |

A per-session "always allow this tool" cache short-circuits to ALLOW.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Protocol

from lca.core.messages import ToolCall
from lca.permissions.modes import DEFAULT_RISK_CEILING, AutonomyMode
from lca.tools.base import RiskLevel


class Decision(StrEnum):
    ALLOW = "allow"
    DENY = "deny"
    ASK = "ask"


class PermissionPolicy(Protocol):
    def evaluate(
        self,
        call: ToolCall,
        risk: RiskLevel,
        mode: AutonomyMode,
        allow_cache: set[str] | None = None,
    ) -> Decision: ...


class DefaultPolicy:
    """The default risk-matrix policy."""

    def __init__(self, autonomous_ceiling: RiskLevel = DEFAULT_RISK_CEILING) -> None:
        self._ceiling = autonomous_ceiling

    def evaluate(
        self,
        call: ToolCall,
        risk: RiskLevel,
        mode: AutonomyMode,
        allow_cache: set[str] | None = None,
    ) -> Decision:
        if risk == RiskLevel.READ:
            return Decision.ALLOW
        if allow_cache and call.name in allow_cache:
            return Decision.ALLOW
        if mode == AutonomyMode.PLAN:
            return Decision.DENY
        if mode == AutonomyMode.AUTONOMOUS:
            return Decision.ALLOW if risk <= self._ceiling else Decision.ASK
        # GATED
        return Decision.ASK
