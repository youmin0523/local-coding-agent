"""The web UI's `Approver`: bridges a gated tool call to an HTTP callback.

When the agent needs approval it emits an `ApprovalRequired` event (carrying the
tool call id) which the browser receives over SSE; the user clicks allow/deny and
the browser POSTs to ``/api/approvals/{id}``, which resolves the awaiting future.
"""

from __future__ import annotations

import asyncio

from lca.core.messages import ToolCall
from lca.tools.base import RiskLevel


class WebApprover:
    def __init__(self) -> None:
        self._pending: dict[str, asyncio.Future[bool]] = {}

    async def request(self, call: ToolCall, risk: RiskLevel, preview: str = "") -> bool:
        loop = asyncio.get_running_loop()
        fut: asyncio.Future[bool] = loop.create_future()
        self._pending[call.id] = fut
        try:
            return await fut
        finally:
            self._pending.pop(call.id, None)

    def resolve(self, request_id: str, approved: bool) -> bool:
        """Resolve a pending approval; returns True if one was waiting."""
        fut = self._pending.get(request_id)
        if fut is not None and not fut.done():
            fut.set_result(approved)
            return True
        return False
