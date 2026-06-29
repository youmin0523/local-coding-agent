"""The `lca` command-line interface (Typer + Rich).

This is a thin UI adapter: it owns no agent logic. Commands construct the core
objects and render their output / event streams. As the agent grows, commands
(`ask`, `chat`, `index`, `mcp`, `memory`, `eval`) are added here, but the
intelligence always lives below `core/`.
"""

from __future__ import annotations

import asyncio
import contextlib
import sys
from pathlib import Path
from typing import Literal

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from lca import __version__
from lca.assembly import attach_mcp, build_agent
from lca.cli.approval import CliApprover
from lca.cli.clipboard import copy_to_clipboard
from lca.cli.render import render_event
from lca.config.paths import index_db_path, memory_db_path
from lca.config.settings import Settings, get_settings
from lca.core.agent import Agent
from lca.core.context import estimate_used_tokens
from lca.core.events import TokenDelta, ToolFinished, TurnFinished
from lca.core.session import Session
from lca.engine_mgmt.doctor import DoctorReport, run_doctor
from lca.evaluation import EvalTask, default_tasks, load_tasks, run_eval
from lca.learning import LearnReport, export_sft, run_rollouts
from lca.memory.store import MemoryStore
from lca.observability.logging import configure_logging
from lca.permissions.approver import AutoApprover
from lca.permissions.modes import AutonomyMode
from lca.rag.embedder import default_embedder
from lca.rag.indexer import Indexer
from lca.rag.store import SqliteVectorStore
from lca.routing.router import Router


def _force_utf8_stdio() -> None:
    """Windows consoles default to a legacy codepage (cp949 on Korean Windows);
    force UTF-8 so Rich output (—, ✓, →, box-drawing) never raises
    UnicodeEncodeError. Safe no-op where the streams can't be reconfigured."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            with contextlib.suppress(ValueError, OSError):  # redirected/closed stream
                reconfigure(encoding="utf-8")


_force_utf8_stdio()

app = typer.Typer(
    name="lca",
    help="lca — a 100% local, verification-grounded coding agent.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()

# Domain task set distilled from the user's own projects (used by learn/eval if present).
_DOMAIN_TASKS = Path("evals/user_domain_tasks.jsonl")


async def _probe_disagreement(settings: Settings, prompt: str) -> float:
    """Sample the fast model a couple of times and score how much the answers diverge."""
    from lca.core.messages import Message
    from lca.providers.base import ChatRequest
    from lca.providers.registry import build_provider, resolve_model
    from lca.routing.consistency import probe_disagreement

    provider = build_provider(settings)
    fast = resolve_model("fast", settings)

    async def sample_once() -> str:
        req = ChatRequest(
            messages=[Message.user(prompt)], model=fast, temperature=0.8, max_tokens=160
        )
        parts = [c.delta_text async for c in provider.chat_stream(req) if c.delta_text]
        return "".join(parts)

    try:
        return await probe_disagreement(sample_once, k=2)
    except Exception:  # a probe failure must never block the turn
        return 0.0


async def _stream_turn(agent: Agent, session: Session, text: str) -> str:
    """Render a turn with a live 'thinking' spinner; return the final answer text.

    The spinner shows while waiting for the model (before the first token, and again
    after each tool while it generates the next step), so it's always clear the agent
    is working — even on the slow 30B.
    """
    parts: list[str] = []
    final = ""
    spinner = console.status("[dim]생각 중…[/]", spinner="dots")
    spinner.start()
    active = True
    try:
        async for event in agent.run_turn(session, text):
            if active:
                spinner.stop()
                active = False
            render_event(console, event)
            if isinstance(event, TokenDelta):
                parts.append(event.text)
            elif isinstance(event, TurnFinished):
                final = event.content or "".join(parts)
            elif isinstance(event, ToolFinished):
                spinner.update("[dim]결과 분석 중…[/]")
                spinner.start()
                active = True
    finally:
        if active:
            spinner.stop()
    return final or "".join(parts)


def _resolve_tasks(tasks_file: str | None) -> list[EvalTask]:
    if tasks_file:
        return load_tasks(Path(tasks_file))
    if _DOMAIN_TASKS.exists():
        return load_tasks(_DOMAIN_TASKS)
    return default_tasks()


@app.command()
def version() -> None:
    """Print the lca version."""
    console.print(f"lca {__version__}")


@app.command()
def config() -> None:
    """Show the effective configuration (engine, profile, models, autonomy)."""
    from lca.providers.registry import detect_base_url

    s = get_settings()
    engine_url = detect_base_url(s.llm.base_url, key=s.llm.api_key)
    table = Table(title="lca config", header_style="bold")
    table.add_column("Setting")
    table.add_column("Value")
    detail = engine_url if engine_url == s.llm.base_url else f"{engine_url}  (auto-detected)"
    table.add_row("engine base_url", detail)
    table.add_row("profile", s.profile)
    table.add_row("brain model", s.llm.brain_model)
    table.add_row("fast model", s.llm.fast_model)
    table.add_row("max context tokens", str(s.llm.max_context_tokens))
    table.add_row("autonomy default", s.autonomy)
    table.add_row("response language", s.response_language)
    table.add_row("verify pass threshold", str(s.verify_pass_threshold))
    table.add_row("searxng url", s.search.searxng_url or "(none)")
    table.add_row("tavily key", "set" if s.search.tavily_api_key else "(none)")
    table.add_row("log", f"{s.log.format} / {s.log.level}")
    console.print(table)


@app.command()
def stats() -> None:
    """Show how much the agent has learned and indexed so far."""
    from lca.memory.store import MemoryStore
    from lca.rag.store import SqliteVectorStore

    mem_db = memory_db_path()
    idx_db = index_db_path()
    learned = MemoryStore(mem_db).count() if mem_db.exists() else 0
    indexed = SqliteVectorStore(idx_db).count() if idx_db.exists() else 0

    table = Table(title="lca stats", header_style="bold")
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    table.add_row("Learned experiences (verified)", str(learned))
    table.add_row("Indexed code chunks", str(indexed))
    console.print(table)
    if learned == 0:
        console.print("[dim]Tip: run tasks with verification/execution so the agent learns.[/]")


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
        True, "--route/--no-route", help="Auto-pick model + verification by difficulty."
    ),
    no_memory: bool = typer.Option(False, "--no-memory", help="Disable experience memory."),
    mcp: bool = typer.Option(
        False, "--mcp", help="Connect local MCP servers (filesystem/git/fetch)."
    ),
    copy: bool = typer.Option(False, "--copy", help="Copy the final answer to the clipboard."),
    md: str = typer.Option("", "--md", help="Also save the final answer to this .md file."),
    model: str = typer.Option(
        "auto", "--model", help="Model: auto (route) | fast (7B) | brain (30B)."
    ),
    notify_done: bool = typer.Option(
        False, "--notify", help="Desktop notification when the turn completes."
    ),
) -> None:
    """Run a single agent turn against the local engine."""
    settings = get_settings()
    configure_logging(settings.log.format, settings.log.level)
    workspace = Path(path).resolve()
    mode = AutonomyMode.AUTONOMOUS if auto else (AutonomyMode.PLAN if plan else AutonomyMode.GATED)

    model_logical: Literal["brain", "fast"] = "brain" if settings.profile == "quality" else "fast"
    do_verify = verify
    samples = 1
    if model == "fast":  # explicit model choice overrides routing
        model_logical = "fast"
        route = False
    elif model == "brain":
        model_logical = "brain"
        route = False
    if route:
        brain = settings.profile == "quality"
        # Self-consistency probe (quality only): a couple of quick fast-model samples;
        # high divergence escalates difficulty so test-time compute lands where it matters.
        disagreement: float | None = None
        if brain and settings.route_consistency_probe:
            disagreement = asyncio.run(_probe_disagreement(settings, prompt))
        rp = Router(brain_available=brain).plan(prompt, disagreement=disagreement)
        model_logical = rp.model
        do_verify = do_verify or rp.verify
        samples = rp.samples
        dis = f", disagree={disagreement}" if disagreement is not None else ""
        console.print(
            f"[dim]route: {rp.difficulty} → {rp.model}, verify={do_verify}, "
            f"samples={samples}{dis}[/]"
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

    async def _run() -> str:
        manager = await attach_mcp(agent, str(workspace)) if mcp else None
        if manager is not None:
            console.print(f"[dim]MCP: {len(agent.registry)} tools available[/]")
        try:
            return await _stream_turn(agent, session, prompt)
        finally:
            if manager is not None:
                await manager.aclose()

    answer = asyncio.run(_run())
    if md and answer:
        out_path = Path(md)
        out_path.write_text(answer, encoding="utf-8")
        console.print(f"[green]Saved[/] answer to {out_path}")
    if copy and answer:
        ok = copy_to_clipboard(answer)
        console.print(
            "[green]Copied to clipboard.[/]" if ok else "[yellow]Clipboard unavailable.[/]"
        )
    if notify_done:
        from lca.cli.notify import notify

        notify("lca — 완료", answer or "처리가 완료되었습니다.")


@app.command(name="mcp")
def mcp_cmd(path: str = typer.Option(".", "--path", "-C", help="Workspace directory.")) -> None:
    """Connect the local MCP servers (filesystem/git/fetch) and list their tools."""
    settings = get_settings()
    configure_logging(settings.log.format, settings.log.level)
    workspace = Path(path).resolve()

    async def _run() -> None:
        from lca.mcp.client import MCPClientManager
        from lca.mcp.servers import default_servers
        from lca.tools.registry import ToolRegistry

        registry = ToolRegistry()
        manager = MCPClientManager()
        try:
            await manager.connect_all(default_servers(str(workspace)), registry)
            names = registry.names()
            if not names:
                console.print(
                    "[yellow]No MCP tools connected.[/] Needs npx/uvx + first-run download."
                )
            else:
                table = Table(title="MCP tools", header_style="bold")
                table.add_column("tool")
                for name in names:
                    table.add_row(name)
                console.print(table)
        finally:
            await manager.aclose()

    asyncio.run(_run())


@app.command(name="skills")
def skills_cmd(path: str = typer.Option(".", "--path", "-C", help="Workspace directory.")) -> None:
    """List the Agent Skills (SKILL.md) available to the agent."""
    from lca.skills.loader import bundled_dir, load_skills

    workspace = Path(path).resolve()
    skills = load_skills(bundled_dir(), workspace / "skills")
    if not skills:
        console.print("[yellow]No skills found.[/] Add <workspace>/skills/<name>/SKILL.md")
        return
    table = Table(title=f"Agent skills ({len(skills)})", header_style="bold")
    table.add_column("name", style="cyan")
    table.add_column("description")
    for s in skills:
        desc = s.description if len(s.description) <= 100 else s.description[:97] + "..."
        table.add_row(s.name, desc)
    console.print(table)


@app.command(name="map")
def repo_map(path: str = typer.Option(".", "--path", "-C", help="Workspace directory.")) -> None:
    """Print a compact whole-repo map: each code file's top-level classes/functions."""
    from lca.tools.base import ToolContext
    from lca.tools.symbols import RepoMapTool

    ws = Path(path).resolve()
    ctx = ToolContext(
        workspace_root=ws, approver=AutoApprover(), session=Session(workspace_root=ws)
    )
    console.print(asyncio.run(RepoMapTool().run({}, ctx)).content)


@app.command()
def undo(
    path: str = typer.Option(".", "--path", "-C", help="Workspace directory."),
    steps: int = typer.Option(1, "--steps", "-n", help="How many edits to undo."),
) -> None:
    """Revert the agent's most recent file edit(s) (checkpointed before each write)."""
    from lca.tools.checkpoint import Checkpointer

    cp = Checkpointer(Path(path).resolve())
    if cp.pending() == 0:
        console.print("[yellow]Nothing to undo.[/]")
        return
    for _ in range(max(1, steps)):
        desc = cp.undo_last()
        if desc is None:
            break
        console.print(f"[green]undo[/] {desc}")
    console.print(f"[dim]{cp.pending()} edit(s) still undoable[/]")


@app.command()
def chat(
    path: str = typer.Option(".", "--path", "-C", help="Workspace directory."),
    auto: bool = typer.Option(False, "--auto", help="Autonomous mode."),
    plan: bool = typer.Option(False, "--plan", help="Plan mode (propose actions, never execute)."),
    verify: bool = typer.Option(False, "--verify", help="Verify answers (deliver-or-abstain)."),
    model: str = typer.Option("auto", "--model", help="Model: auto | fast (7B) | brain (30B)."),
    notify_done: bool = typer.Option(False, "--notify", help="Desktop notification per turn."),
) -> None:
    """Interactive multi-turn chat. 'exit'/Ctrl-D to quit · '/model fast|brain|auto' to switch."""
    settings = get_settings()
    configure_logging(settings.log.format, settings.log.level)
    workspace = Path(path).resolve()
    mode = AutonomyMode.AUTONOMOUS if auto else (AutonomyMode.PLAN if plan else AutonomyMode.GATED)

    def _resolve_model(choice: str) -> Literal["brain", "fast"]:
        if choice in ("fast", "brain"):
            return choice  # type: ignore[return-value]
        return "brain" if settings.profile == "quality" else "fast"

    def _build(ml: Literal["brain", "fast"]) -> Agent:
        return build_agent(CliApprover(console), settings=settings, model_logical=ml, verify=verify)

    current = _resolve_model(model)
    agent = _build(current)
    session = Session(
        workspace_root=workspace, mode=mode, token_budget=settings.llm.max_context_tokens
    )
    console.print(
        f"[dim]lca chat ({current}) — 'exit'/Ctrl-D to quit · '/model fast|brain|auto' to switch[/]"
    )

    async def _turn(text: str) -> None:
        await _stream_turn(agent, session, text)
        used = estimate_used_tokens(session)
        pct = min(100, round(used / session.token_budget * 100))
        console.print(
            f"[dim]🧠 context ~{used / 1000:.1f}K/{session.token_budget // 1000}K ({pct}%)[/]"
        )
        if notify_done:
            from lca.cli.notify import notify

            notify("lca — 응답 완료", "처리가 완료되었습니다.")

    while True:
        try:
            user_input = console.input("\n[bold green]you[/] > ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]bye[/]")
            break
        if user_input.lower() in {"exit", "quit", ":q"}:
            break
        if user_input.startswith("/model"):
            parts = user_input.split()
            current = _resolve_model(parts[1] if len(parts) > 1 else "auto")
            agent = _build(current)
            console.print(f"[dim]model → {current}[/]")
            continue
        if user_input:
            asyncio.run(_turn(user_input))

    snap = agent.metrics_snapshot()
    c = snap.counters
    if c.get("tool_calls"):
        validity = 1 - c.get("tool_failures", 0) / c["tool_calls"]
        console.print(
            f"[dim]session: {c.get('turns', 0)} turns · {c['tool_calls']} tool calls "
            f"({validity:.0%} ok) · {c.get('abstained', 0)} abstained[/]"
        )


@app.command()
def web(
    path: str = typer.Option(".", "--path", "-C", help="Workspace directory."),
    host: str = typer.Option("127.0.0.1", help="Bind host."),
    port: int = typer.Option(8765, help="Bind port."),
    open_browser: bool = typer.Option(
        True, "--open/--no-open", help="Open the browser automatically."
    ),
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
    url = f"http://{host}:{port}"
    console.print(f"[green]lca web[/] → {url}  (Ctrl-C to stop)")
    if open_browser:
        # Open the browser shortly after the server starts accepting connections.
        import threading
        import webbrowser

        threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    uvicorn.run(application, host=host, port=port, log_level="warning")


@app.command(name="learn")
def learn(
    path: str = typer.Option(".", "--path", "-C", help="Workspace directory."),
    tasks_file: str | None = typer.Option(None, "--tasks", help="JSONL task file (optional)."),
    samples: int = typer.Option(3, "--samples", help="Best-of-N candidates per rollout."),
) -> None:
    """Self-improve (RLVR): run tasks, keep verified trajectories, build the SFT corpus.

    Rollout → execution/verification reward → keep passes (memory) → export dataset.
    The gradient step (QLoRA) is the optional WSL2 stage; see docs/runbook-training-wsl2.md.
    """
    settings = get_settings()
    configure_logging(settings.log.format, settings.log.level)
    workspace = Path(path).resolve()
    tasks = _resolve_tasks(tasks_file)
    model_logical: Literal["brain", "fast"] = "brain" if settings.profile == "quality" else "fast"

    def factory() -> Agent:
        return build_agent(
            AutoApprover(),
            settings=settings,
            model_logical=model_logical,
            verify=True,
            samples=samples,
            use_memory=True,
        )

    async def _run() -> LearnReport:
        with console.status(f"Rolling out {len(tasks)} task(s) with best-of-{samples} + verify…"):
            rewarded = await run_rollouts(factory, tasks, workspace)
        store = MemoryStore(memory_db_path())
        out = Path("training") / "data" / "sft.jsonl"
        examples = export_sft(store, out)
        return LearnReport(
            rollouts=len(tasks),
            rewarded=rewarded,
            learned_total=store.count(),
            dataset_path=str(out),
            dataset_examples=examples,
        )

    report = asyncio.run(_run())
    table = Table(title="lca learn (RLVR rollout)", header_style="bold")
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    table.add_row("Rollouts", str(report.rollouts))
    table.add_row("Rewarded (verified pass)", f"{report.rewarded}  ({report.reward_rate:.0%})")
    table.add_row("Learned experiences (total)", str(report.learned_total))
    table.add_row("SFT examples written", str(report.dataset_examples))
    console.print(table)
    console.print(f"[dim]dataset: {report.dataset_path}[/]")
    console.print(
        "[dim]next (optional, WSL2): python training/train_qlora.py "
        "--data training/data/sft.jsonl  — see docs/runbook-training-wsl2.md[/]"
    )


@app.command(name="eval")
def evaluate(
    path: str = typer.Option(".", "--path", "-C", help="Workspace directory."),
    tasks_file: str | None = typer.Option(None, "--tasks", help="JSONL task file (optional)."),
    verify: bool = typer.Option(True, "--verify/--no-verify", help="Verify answers during eval."),
    samples: int = typer.Option(
        1,
        "--samples",
        help="Best-of-N candidates per task (stabilizes the noisy single-sample run).",
    ),
) -> None:
    """Run the eval suite against the local engine and print a scorecard."""
    settings = get_settings()
    configure_logging(settings.log.format, settings.log.level)
    workspace = Path(path).resolve()
    tasks = _resolve_tasks(tasks_file)
    model_logical: Literal["brain", "fast"] = "brain" if settings.profile == "quality" else "fast"

    def factory() -> Agent:
        return build_agent(
            AutoApprover(),
            settings=settings,
            model_logical=model_logical,
            verify=verify,
            samples=samples,
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
