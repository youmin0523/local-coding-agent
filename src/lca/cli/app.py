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
from lca.assembly import build_agent
from lca.cli.approval import CliApprover
from lca.cli.render import render_event
from lca.config.paths import index_db_path
from lca.config.settings import get_settings
from lca.core.agent import Agent
from lca.core.session import Session
from lca.engine_mgmt.doctor import DoctorReport, run_doctor
from lca.evaluation import default_tasks, load_tasks, run_eval
from lca.observability.logging import configure_logging
from lca.permissions.approver import AutoApprover
from lca.permissions.modes import AutonomyMode
from lca.rag.embedder import default_embedder
from lca.rag.indexer import Indexer
from lca.rag.store import SqliteVectorStore
from lca.routing.router import Router

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
    verify: bool = typer.Option(
        False, "--verify", help="Verify the final answer (deliver-or-abstain)."
    ),
    route: bool = typer.Option(
        False, "--route", help="Auto-pick model + verification by difficulty."
    ),
    no_memory: bool = typer.Option(False, "--no-memory", help="Disable experience memory."),
) -> None:
    """Run a single agent turn against the local engine."""
    settings = get_settings()
    configure_logging(settings.log.format, settings.log.level)
    workspace = Path(path).resolve()
    mode = AutonomyMode.AUTONOMOUS if auto else (AutonomyMode.PLAN if plan else AutonomyMode.GATED)

    model_logical: Literal["brain", "fast"] = "brain" if settings.profile == "quality" else "fast"
    do_verify = verify
    samples = 1
    if route:
        rp = Router().plan(prompt)
        model_logical = rp.model
        do_verify = do_verify or rp.verify
        samples = rp.samples
        console.print(
            f"[dim]route: {rp.difficulty} → {rp.model}, verify={do_verify}, samples={samples}[/]"
        )

    agent = build_agent(
        CliApprover(console),
        settings=settings,
        model_logical=model_logical,
        verify=do_verify,
        samples=samples,
        use_memory=not no_memory,
    )
    session = Session(
        workspace_root=workspace, mode=mode, token_budget=settings.llm.max_context_tokens
    )

    async def _run() -> None:
        async for event in agent.run_turn(session, prompt):
            render_event(console, event)

    asyncio.run(_run())


@app.command()
def chat(
    path: str = typer.Option(".", "--path", "-C", help="Workspace directory."),
    auto: bool = typer.Option(False, "--auto", help="Autonomous mode."),
    verify: bool = typer.Option(False, "--verify", help="Verify answers (deliver-or-abstain)."),
) -> None:
    """Interactive multi-turn chat (one persistent session). Ctrl-D / 'exit' to quit."""
    settings = get_settings()
    configure_logging(settings.log.format, settings.log.level)
    workspace = Path(path).resolve()
    mode = AutonomyMode.AUTONOMOUS if auto else AutonomyMode.GATED
    model_logical: Literal["brain", "fast"] = "brain" if settings.profile == "quality" else "fast"
    agent = build_agent(
        CliApprover(console), settings=settings, model_logical=model_logical, verify=verify
    )
    session = Session(
        workspace_root=workspace, mode=mode, token_budget=settings.llm.max_context_tokens
    )
    console.print("[dim]lca chat — type 'exit' or Ctrl-D to quit.[/]")

    async def _turn(text: str) -> None:
        async for event in agent.run_turn(session, text):
            render_event(console, event)

    while True:
        try:
            user_input = console.input("\n[bold green]you[/] › ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]bye[/]")
            break
        if user_input.lower() in {"exit", "quit", ":q"}:
            break
        if user_input:
            asyncio.run(_turn(user_input))


@app.command()
def web(
    path: str = typer.Option(".", "--path", "-C", help="Workspace directory."),
    host: str = typer.Option("127.0.0.1", help="Bind host."),
    port: int = typer.Option(8765, help="Bind port."),
) -> None:
    """Serve the browser chat UI (requires the `web` extra)."""
    settings = get_settings()
    configure_logging(settings.log.format, settings.log.level)
    try:
        import uvicorn

        from lca.web.server import create_app
    except ImportError:
        console.print("[red]Web UI requires:[/] uv sync --extra web")
        raise typer.Exit(code=1) from None
    application = create_app(workspace=Path(path).resolve())
    console.print(f"[green]lca web[/] → http://{host}:{port}")
    uvicorn.run(application, host=host, port=port, log_level="warning")


@app.command(name="eval")
def evaluate(
    path: str = typer.Option(".", "--path", "-C", help="Workspace directory."),
    tasks_file: str | None = typer.Option(None, "--tasks", help="JSONL task file (optional)."),
    verify: bool = typer.Option(True, "--verify/--no-verify", help="Verify answers during eval."),
) -> None:
    """Run the eval suite against the local engine and print a scorecard."""
    settings = get_settings()
    configure_logging(settings.log.format, settings.log.level)
    workspace = Path(path).resolve()
    tasks = load_tasks(Path(tasks_file)) if tasks_file else default_tasks()
    model_logical: Literal["brain", "fast"] = "brain" if settings.profile == "quality" else "fast"

    def factory() -> Agent:
        return build_agent(
            AutoApprover(),
            settings=settings,
            model_logical=model_logical,
            verify=verify,
            use_memory=False,
        )

    scorecard = asyncio.run(run_eval(factory, tasks, workspace))

    table = Table(title="lca eval", header_style="bold")
    table.add_column("task")
    table.add_column("result")
    table.add_column("detail")
    for r in scorecard.results:
        mark = "[green]PASS[/]" if r.passed else "[red]FAIL[/]"
        table.add_row(r.id, mark, r.detail or ("abstained" if r.abstained else ""))
    console.print(table)
    console.print(
        f"pass rate [bold]{scorecard.pass_rate:.0%}[/] "
        f"({scorecard.passed}/{scorecard.total}) · "
        f"tool validity {scorecard.tool_validity:.0%} "
        f"({scorecard.tool_calls - scorecard.tool_failures}/{scorecard.tool_calls})"
    )


def main() -> None:
    app()


if __name__ == "__main__":
    main()
