"""Render the agent's `AgentEvent` stream to the terminal with Rich."""

from __future__ import annotations

from rich.console import Console
from rich.syntax import Syntax

from lca.core.events import (
    Abstained,
    AgentEvent,
    ErrorEvent,
    ReflectionNote,
    TokenDelta,
    ToolFinished,
    ToolStarted,
    TurnFinished,
    VerificationResult,
)


def render_event(console: Console, event: AgentEvent) -> None:
    if isinstance(event, TokenDelta):
        console.print(event.text, end="", soft_wrap=True)
    elif isinstance(event, ToolStarted):
        console.print(f"\n[cyan]→ {event.name}[/]")
    elif isinstance(event, ToolFinished):
        status = "[green]ok[/]" if event.result.ok else "[red]failed[/]"
        console.print(f"  {status}")
        for artifact in event.result.artifacts:
            if artifact.kind == "diff" and artifact.body:
                console.print(Syntax(artifact.body, "diff", theme="ansi_dark", word_wrap=True))
    elif isinstance(event, VerificationResult):
        console.print(
            f"\n[magenta]verified[/] {event.verdict} "
            f"(confidence {event.confidence:.2f}) {event.detail}"
        )
    elif isinstance(event, Abstained):
        console.print(f"\n[yellow]Not confident:[/] {event.reason}")
        for opt in event.options:
            console.print(f"  · {opt}")
    elif isinstance(event, ReflectionNote):
        console.print(f"\n[dim]reflection: {event.text}[/]")
    elif isinstance(event, ErrorEvent):
        console.print(f"\n[red]error:[/] {event.message}")
    elif isinstance(event, TurnFinished):
        if event.stop_reason != "complete":
            console.print(f"\n[dim](stopped: {event.stop_reason})[/]")
        console.print()
