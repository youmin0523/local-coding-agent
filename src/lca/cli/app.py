"""The `lca` command-line interface (Typer + Rich).

This is a thin UI adapter: it owns no agent logic. Commands construct the core
objects and render their output / event streams. As the agent grows, commands
(`ask`, `chat`, `index`, `mcp`, `memory`, `eval`) are added here, but the
intelligence always lives below `core/`.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Literal

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from lca import __version__
from lca.cli.approval import CliApprover
from lca.cli.render import render_event
from lca.config.paths import index_db_path
from lca.config.settings import get_settings
from lca.core.agent import Agent
from lca.core.session import Session
from lca.engine_mgmt.doctor import DoctorReport, run_doctor
from lca.observability.logging import configure_logging
from lca.permissions.modes import AutonomyMode
from lca.permissions.policy import DefaultPolicy
from lca.providers.registry import build_provider, resolve_model
from lca.rag.embedder import default_embedder
from lca.rag.hybrid import HybridRetriever
from lca.rag.indexer import Indexer
from lca.rag.retriever import Retriever
from lca.rag.store import SqliteVectorStore
from lca.tools import build_default_registry

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


@app.command()
def index(path: str = typer.Argument(".", help="Workspace directory to index.")) -> None:
    """Build/refresh the local code index used for retrieval (RAG)."""
    settings = get_settings()
    configure_logging(settings.log.format, settings.log.level)
    root = Path(path).resolve()
    store = SqliteVectorStore(index_db_path())
    indexer = Indexer(store, default_embedder(), root=root)
    with console.status(f"Indexing {root}…"):
        stats = indexer.index_all()
    store.close()
    console.print(
        f"[green]Indexed[/] {stats.files_indexed} file(s) "
        f"({stats.chunks} chunks), skipped {stats.files_skipped}, removed {stats.files_removed}."
    )


@app.command()
def ask(
    prompt: str = typer.Argument(..., help="What you want the agent to do."),
    path: str = typer.Option(".", "--path", "-C", help="Workspace directory."),
    auto: bool = typer.Option(False, "--auto", help="Autonomous mode (auto-approve ≤ ceiling)."),
    plan: bool = typer.Option(False, "--plan", help="Plan mode (propose actions, never execute)."),
) -> None:
    """Run a single agent turn against the local engine."""
    settings = get_settings()
    configure_logging(settings.log.format, settings.log.level)
    workspace = Path(path).resolve()
    mode = AutonomyMode.AUTONOMOUS if auto else (AutonomyMode.PLAN if plan else AutonomyMode.GATED)

    retriever = _open_retriever()
    provider = build_provider(settings)
    logical: Literal["brain", "fast"] = "brain" if settings.profile == "quality" else "fast"
    agent = Agent(
        provider,
        build_default_registry(retriever),
        DefaultPolicy(),
        CliApprover(console),
        model=resolve_model(logical, settings),
        retriever=retriever,
    )
    session = Session(
        workspace_root=workspace, mode=mode, token_budget=settings.llm.max_context_tokens
    )

    async def _run() -> None:
        async for event in agent.run_turn(session, prompt):
            render_event(console, event)

    asyncio.run(_run())


def _open_retriever() -> Retriever | None:
    """Open the on-disk index as a retriever, if one has been built."""
    db = index_db_path()
    if not db.exists():
        return None
    store = SqliteVectorStore(db)
    return HybridRetriever(store, default_embedder())


def main() -> None:
    app()


if __name__ == "__main__":
    main()
