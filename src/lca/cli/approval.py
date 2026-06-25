"""The CLI's implementation of the `Approver` interface — a Rich prompt."""

from __future__ import annotations

import sys

from rich.console import Console
from rich.prompt import Prompt

from lca.core.messages import ToolCall
from lca.tools.base import RiskLevel


class CliApprover:
    """Prompts the user to allow/deny a gated tool call in the terminal."""

    def __init__(self, console: Console, session_allow_cache: set[str] | None = None) -> None:
        self._console = console
        self._allow_cache = session_allow_cache if session_allow_cache is not None else set()

    async def request(self, call: ToolCall, risk: RiskLevel) -> bool:
        if call.name in self._allow_cache:
            return True
        # Fail safe: with no interactive terminal (piped / background run) we cannot
        # ask, so deny rather than hang forever. Use --auto for unattended runs.
        if not sys.stdin.isatty():
            self._console.print(
                f"[yellow]Auto-denied[/] {call.name} ({risk.name}): no interactive terminal "
                "(use --auto for unattended runs)."
            )
            return False
        self._console.print(
            f"\n[yellow]Approval required[/] · [bold]{call.name}[/] "
            f"([red]{risk.name}[/]) args={call.arguments}"
        )
        choice = Prompt.ask("  allow?", choices=["y", "n", "a"], default="n")
        if choice == "a":
            self._allow_cache.add(call.name)
            return True
        return choice == "y"
