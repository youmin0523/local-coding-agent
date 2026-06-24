"""The `lca` command-line interface (Typer + Rich).

This is a thin UI adapter: it owns no agent logic. Commands construct the core
objects and render their output / event streams. As the agent grows, commands
(`ask`, `chat`, `index`, `mcp`, `memory`, `eval`) are added here, but the
intelligence always lives below `core/`.
"""

from __future__ import annotations

import asyncio

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from lca import __version__
from lca.config.settings import get_settings
from lca.engine_mgmt.doctor import DoctorReport, run_doctor
from lca.observability.logging import configure_logging

app = typer.Typer(
    name="lca",
    help="lca — a 100% local, verification-grounded coding agent.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()


@app.command()
def version() -> None:
    """Print the lca version."""
    console.print(f"lca {__version__}")


@app.command()
def doctor() -> None:
    """Diagnose the GPU and inference engine before relying on them.

    Verifies a discrete NVIDIA GPU is present, the engine endpoint is reachable,
    and the context window is sane for an 8GB card. Run this first.
    """
    settings = get_settings()
    configure_logging(settings.log.format, settings.log.level)
    report = asyncio.run(run_doctor(settings))
    _render_doctor(report)
    raise typer.Exit(code=0 if report.ok else 1)


def _render_doctor(report: DoctorReport) -> None:
    table = Table(title="lca doctor", show_header=True, header_style="bold")
    table.add_column("Check")
    table.add_column("Result")

    if report.gpus:
        for g in report.gpus:
            vram = f"{g.vram_free_mb}/{g.vram_total_mb} MB free" if g.vram_total_mb else "?"
            table.add_row(f"GPU · {g.name}", f"{vram} · driver {g.driver_version}")
    else:
        table.add_row("GPU", "[yellow]nvidia-smi reported no GPUs[/]")

    table.add_row(
        "Discrete GPU",
        "[green]present[/]" if report.discrete_gpu_present else "[red]not detected[/]",
    )
    engine = report.engine
    table.add_row(
        "Engine",
        f"[green]reachable[/] ({', '.join(engine.models) or 'no models'})"
        if engine.reachable
        else f"[red]unreachable[/] — {engine.detail}",
    )
    if engine.context_window:
        table.add_row("Context window", f"{engine.context_window} tokens")
    table.add_row("Context budget", f"{report.context_budget} tokens")

    console.print(table)
    for note in report.notes:
        console.print(f"  [dim]·[/] {note}")
    for warning in report.warnings:
        console.print(f"  [yellow]![/] {warning}")
    verdict = "[green]READY[/]" if report.ok else "[red]NOT READY[/]"
    console.print(Panel(verdict, title="Verdict", expand=False))


def main() -> None:
    app()


if __name__ == "__main__":
    main()
