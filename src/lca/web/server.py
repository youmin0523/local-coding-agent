"""FastAPI backend for the web UI.

Exposes the same agent the CLI uses over three small endpoints:

* ``POST /api/runs`` — start a turn, returns a run id;
* ``GET  /api/runs/{id}/events`` — Server-Sent Events stream of `AgentEvent`s;
* ``POST /api/approvals/{request_id}`` — allow/deny a gated tool call.

The agent is built per-run via the shared composition root (`assembly.build_agent`)
so behavior matches the CLI exactly; an `agent_builder` override is accepted for
tests (inject a FakeProvider-backed agent, no GPU).
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Callable
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from lca.assembly import build_agent
from lca.config.settings import get_settings
from lca.core.agent import Agent
from lca.core.session import Session
from lca.observability.logging import get_logger
from lca.permissions.modes import AutonomyMode
from lca.routing.router import Router
from lca.web.approver import WebApprover

log = get_logger("web.server")

# (approver, user_message) -> Agent, so the default builder can route by difficulty.
AgentBuilder = Callable[[WebApprover, str], Agent]
_FRONTEND = Path(__file__).parent / "frontend"


class RunRequest(BaseModel):
    message: str
    mode: str = "gated"


class ApprovalRequest(BaseModel):
    approved: bool


class _Run:
    def __init__(
        self, approver: WebApprover, queue: asyncio.Queue[dict[str, object] | None]
    ) -> None:
        self.approver = approver
        self.queue = queue
        self.task: asyncio.Task[None] | None = None


class RunManager:
    def __init__(self, session: Session, agent_builder: AgentBuilder) -> None:
        self._session = session
        self._build = agent_builder
        self._runs: dict[str, _Run] = {}
        self._counter = 0

    def start(self, message: str, mode: str) -> str:
        self._counter += 1
        run_id = f"run{self._counter}"
        approver = WebApprover()
        agent = self._build(approver, message)
        try:
            self._session.mode = AutonomyMode(mode)
        except ValueError:
            self._session.mode = AutonomyMode.GATED
        queue: asyncio.Queue[dict[str, object] | None] = asyncio.Queue()
        run = _Run(approver, queue)
        self._runs[run_id] = run

        async def drive() -> None:
            try:
                async for event in agent.run_turn(self._session, message):
                    await queue.put(event.model_dump())
            except Exception as exc:  # report, never hang the stream
                log.exception("web.run_failed")
                await queue.put({"type": "error", "message": str(exc), "recoverable": False})
            finally:
                await queue.put(None)

        run.task = asyncio.create_task(drive())
        return run_id

    def exists(self, run_id: str) -> bool:
        return run_id in self._runs

    async def stream(self, run_id: str) -> AsyncIterator[dict[str, object]]:
        run = self._runs[run_id]
        while True:
            event = await run.queue.get()
            if event is None:
                break
            yield event
        self._runs.pop(run_id, None)

    def resolve(self, request_id: str, approved: bool) -> bool:
        return any(run.approver.resolve(request_id, approved) for run in self._runs.values())


def _routing_builder() -> AgentBuilder:
    """Default builder: route each message by difficulty (smart by default).

    Respects the configured profile — the 30B brain is only used when profile is
    "quality" (and thus loaded); otherwise it stays on the fast model but still
    escalates verification / best-of-N for harder messages.
    """
    settings = get_settings()
    brain = settings.profile == "quality"
    router = Router(brain_available=brain)

    def build(approver: WebApprover, message: str) -> Agent:
        plan = router.plan(message)
        return build_agent(
            approver,
            settings=settings,
            model_logical=plan.model,
            verify=plan.verify,
            samples=plan.samples,
        )

    return build


def create_app(
    *,
    workspace: Path,
    agent_builder: AgentBuilder | None = None,
) -> FastAPI:
    session = Session(workspace_root=workspace)
    builder: AgentBuilder = agent_builder or _routing_builder()
    manager = RunManager(session, builder)
    app = FastAPI(title="lca", version="0.1.0")

    @app.post("/api/runs")
    async def start_run(req: RunRequest) -> dict[str, str]:
        return {"run_id": manager.start(req.message, req.mode)}

    @app.get("/api/runs/{run_id}/events")
    async def events(run_id: str) -> EventSourceResponse:
        if not manager.exists(run_id):
            raise HTTPException(status_code=404, detail="unknown run")

        async def source() -> AsyncIterator[dict[str, str]]:
            async for event in manager.stream(run_id):
                yield {"data": json.dumps(event)}

        return EventSourceResponse(source())

    @app.post("/api/approvals/{request_id}")
    async def approve(request_id: str, req: ApprovalRequest) -> dict[str, bool]:
        return {"resolved": manager.resolve(request_id, req.approved)}

    @app.get("/", response_class=HTMLResponse)
    async def index() -> str:
        return (_FRONTEND / "index.html").read_text("utf-8")

    return app
