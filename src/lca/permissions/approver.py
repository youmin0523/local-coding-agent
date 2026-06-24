"""The approval interface.

`Approver` is implemented by each UI: the CLI shows a Rich prompt, the web backend
emits an event and awaits an HTTP callback. The core only ever sees this Protocol,
so it never needs to know how a human said yes.

Two trivial implementations live here for tests and non-interactive runs.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from lca.core.messages import ToolCall
from lca.tools.base import RiskLevel


@runtime_checkable
class Approver(Protocol):
    async def request(self, call: ToolCall, risk: RiskLevel) -> bool:
        """Return True to allow the tool call, False to deny it."""
        ...


class AutoApprover:
    """Approves everything. Used in AUTONOMOUS mode (under the policy ceiling) and tests."""

    async def request(self, call: ToolCall, risk: RiskLevel) -> bool:
        return True


class DenyingApprover:
    """Denies everything. Useful for PLAN mode and safety tests."""

    async def request(self, call: ToolCall, risk: RiskLevel) -> bool:
        return False
