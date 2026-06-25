"""CliApprover fail-safe: deny (never hang) when there's no interactive terminal."""

from __future__ import annotations

from rich.console import Console

from lca.cli.approval import CliApprover
from lca.core.messages import ToolCall
from lca.tools.base import RiskLevel


async def test_denies_when_no_tty():
    # Under pytest, stdin is not a tty → request must return False without blocking.
    approver = CliApprover(Console())
    call = ToolCall(id="1", name="write_file", arguments={})
    assert await approver.request(call, RiskLevel.WRITE) is False


async def test_allow_cache_bypasses_prompt():
    approver = CliApprover(Console(), session_allow_cache={"write_file"})
    call = ToolCall(id="1", name="write_file", arguments={})
    assert await approver.request(call, RiskLevel.WRITE) is True
