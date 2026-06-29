"""FastAPI backend for the web UI.

Exposes the same agent the CLI uses. Conversations are first-class: the user can
keep several (one per purpose), each with its own `Session`, persisted to disk so
they survive a server restart.

Endpoints:
* ``GET  /api/conversations``            — list conversations (newest first)
* ``POST /api/conversations``            — create a new conversation
* ``GET  /api/conversations/{id}``       — its message history
* ``DELETE /api/conversations/{id}``     — delete it
* ``POST /api/runs``                     — start a turn (in a conversation); returns a run id
* ``GET  /api/runs/{id}/events``         — SSE stream of `AgentEvent`s
* ``POST /api/approvals/{request_id}``   — allow/deny a gated tool call

The agent is built per-run via the shared composition root (`assembly.build_agent`)
so behavior matches the CLI; an `agent_builder` override is accepted for tests.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from collections.abc import AsyncIterator, Callable
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from lca.assembly import build_agent
from lca.config.settings import get_settings
from lca.core.agent import Agent
from lca.core.messages import Message
from lca.core.session import Session
from lca.observability.logging import get_logger
from lca.permissions.modes import AutonomyMode
from lca.routing.router import Router
from lca.tools.checkpoint import Checkpointer
from lca.web.approver import WebApprover

log = get_logger("web.server")

AgentBuilder = Callable[[WebApprover, str, str], Agent]  # (approver, message, model_choice)
_FRONTEND = Path(__file__).parent / "frontend"
_NEW_TITLE = "새 채팅"


class RunRequest(BaseModel):
    message: str
    mode: str = "gated"
    conversation_id: str = ""
    model: str = "auto"  # "auto" (route by difficulty) | "fast" (7B) | "brain" (30B)
    tdd: bool = False  # test-first: write a failing test, then implement to green


class ApprovalRequest(BaseModel):
    approved: bool


class NewConversation(BaseModel):
    title: str = _NEW_TITLE


class _Run:
    def __init__(
        self, approver: WebApprover, queue: asyncio.Queue[dict[str, object] | None]
    ) -> None:
        self.approver = approver
        self.queue = queue
        self.task: asyncio.Task[None] | None = None


class _Conversation:
    def __init__(self, cid: str, title: str, session: Session, created: float) -> None:
        self.id = cid
        self.title = title
        self.session = session
        self.created = created


class ConversationManager:
    """Holds multiple conversations (each a Session), persisted under .lca/conversations."""

    def __init__(self, workspace: Path, agent_builder: AgentBuilder) -> None:
        self._workspace = workspace
        self._build = agent_builder
        self._convos: dict[str, _Conversation] = {}
        self._runs: dict[str, _Run] = {}
        self._counter = 0
        self._dir = workspace / ".lca" / "conversations"
        self._load_all()
        if not self._convos:
            self.create()

    # ---- persistence -------------------------------------------------------
    def _path(self, cid: str) -> Path:
        return self._dir / f"{cid}.json"

    def _persist(self, conv: _Conversation) -> None:
        try:
            self._dir.mkdir(parents=True, exist_ok=True)
            payload = {
                "id": conv.id,
                "title": conv.title,
                "created": conv.created,
                "messages": [m.model_dump() for m in conv.session.history],
            }
            self._path(conv.id).write_text(json.dumps(payload, ensure_ascii=False), "utf-8")
        except OSError as exc:
            log.warning("web.persist_failed", error=str(exc))

    def _load_all(self) -> None:
        if not self._dir.is_dir():
            return
        for path in self._dir.glob("*.json"):
            try:
                data = json.loads(path.read_text("utf-8"))
                session = Session(workspace_root=self._workspace)
                for raw in data.get("messages", []):
                    session.add(Message.model_validate(raw))
                conv = _Conversation(
                    data["id"],
                    data.get("title", _NEW_TITLE),
                    session,
                    float(data.get("created", 0)),
                )
                self._convos[conv.id] = conv
            except (OSError, ValueError, KeyError) as exc:
                log.warning("web.load_failed", path=str(path), error=str(exc))

    # ---- conversation CRUD -------------------------------------------------
    def create(self, title: str = _NEW_TITLE) -> str:
        cid = uuid.uuid4().hex[:8]
        conv = _Conversation(cid, title, Session(workspace_root=self._workspace), time.time())
        self._convos[cid] = conv
        self._persist(conv)
        return cid

    def summaries(self) -> list[dict[str, str]]:
        ordered = sorted(self._convos.values(), key=lambda c: c.created, reverse=True)
        return [{"id": c.id, "title": c.title} for c in ordered]

    def messages(self, cid: str) -> list[dict[str, str]]:
        conv = self._convos.get(cid)
        if conv is None:
            raise HTTPException(status_code=404, detail="unknown conversation")
        out: list[dict[str, str]] = []
        for m in conv.session.history:
            if m.role in ("user", "assistant") and m.content:
                out.append({"role": m.role, "content": m.content})
        return out

    def delete(self, cid: str) -> None:
        self._convos.pop(cid, None)
        self._path(cid).unlink(missing_ok=True)
        if not self._convos:
            self.create()

    def _resolve(self, cid: str) -> _Conversation:
        if cid and cid in self._convos:
            return self._convos[cid]
        # fall back to the most recent conversation
        return sorted(self._convos.values(), key=lambda c: c.created, reverse=True)[0]

    # ---- runs --------------------------------------------------------------
    def start(
        self,
        message: str,
        mode: str,
        conversation_id: str = "",
        model: str = "auto",
        tdd: bool = False,
    ) -> tuple[str, str, int]:
        conv = self._resolve(conversation_id)
        if conv.title == _NEW_TITLE and message.strip():
            conv.title = message.strip()[:40]
        self._counter += 1
        run_id = f"run{self._counter}"
        approver = WebApprover()
        agent = self._build(approver, message, model)
        conv.session.tdd = tdd
        try:
            conv.session.mode = AutonomyMode(mode)
        except ValueError:
            conv.session.mode = AutonomyMode.GATED
        queue: asyncio.Queue[dict[str, object] | None] = asyncio.Queue()
        run = _Run(approver, queue)
        self._runs[run_id] = run

        async def drive() -> None:
            try:
                async for event in agent.run_turn(conv.session, message):
                    await queue.put(event.model_dump())
            except asyncio.CancelledError:  # stop() / client disconnect → tell the UI, then unwind
                await queue.put({"type": "turn_finished", "stop_reason": "stopped", "content": ""})
                raise
            except Exception as exc:  # report, never hang the stream
                log.exception("web.run_failed")
                await queue.put({"type": "error", "message": str(exc), "recoverable": False})
            finally:
                self._persist(conv)
                await queue.put(None)

        run.task = asyncio.create_task(drive())
        return run_id, conv.id, conv.session.token_budget

    def exists(self, run_id: str) -> bool:
        return run_id in self._runs

    def active_runs(self) -> int:
        """How many runs are still executing (used to block undo mid-edit)."""
        return sum(1 for r in self._runs.values() if r.task and not r.task.done())

    def stop(self, run_id: str) -> bool:
        """Cancel an in-flight run; the drive task's finally still persists + ends the stream."""
        run = self._runs.get(run_id)
        if run and run.task and not run.task.done():
            run.task.cancel()
            return True
        return False

    async def stream(self, run_id: str) -> AsyncIterator[dict[str, object]]:
        run = self._runs.get(run_id)
        if run is None:
            return
        try:
            while True:
                event = await run.queue.get()
                if event is None:
                    break
                yield event
        finally:
            # Always reclaim the run — even if the client disconnects mid-stream (the
            # generator is cancelled here) — and cancel an orphaned drive task so it
            # can't keep running with no consumer.
            if run.task and not run.task.done():
                run.task.cancel()
            self._runs.pop(run_id, None)

    def resolve(self, request_id: str, approved: bool) -> bool:
        return any(run.approver.resolve(request_id, approved) for run in self._runs.values())


def _routing_builder() -> AgentBuilder:
    """Default builder: route each message by difficulty (smart by default)."""
    settings = get_settings()
    router = Router(brain_available=settings.profile == "quality")

    def build(approver: WebApprover, message: str, model: str = "auto") -> Agent:
        # explicit user choice — skip routing (pass literals so the type narrows)
        if model == "fast":
            return build_agent(approver, settings=settings, model_logical="fast", verify=False)
        if model == "brain":
            return build_agent(approver, settings=settings, model_logical="brain", verify=False)
        plan = router.plan(message)  # auto: route by difficulty
        return build_agent(
            approver,
            settings=settings,
            model_logical=plan.model,
            verify=plan.verify,
            samples=plan.samples,
        )

    return build


def create_app(*, workspace: Path, agent_builder: AgentBuilder | None = None) -> FastAPI:
    builder: AgentBuilder = agent_builder or _routing_builder()
    manager = ConversationManager(workspace, builder)
    app = FastAPI(title="lca", version="0.1.0")

    @app.get("/api/conversations")
    async def list_conversations() -> dict[str, list[dict[str, str]]]:
        return {"conversations": manager.summaries()}

    @app.post("/api/conversations")
    async def new_conversation(req: NewConversation) -> dict[str, str]:
        return {"id": manager.create(req.title or _NEW_TITLE)}

    @app.get("/api/conversations/{cid}")
    async def get_conversation(cid: str) -> dict[str, list[dict[str, str]]]:
        return {"messages": manager.messages(cid)}

    @app.delete("/api/conversations/{cid}")
    async def delete_conversation(cid: str) -> dict[str, bool]:
        manager.delete(cid)
        return {"deleted": True}

    @app.post("/api/runs")
    async def start_run(req: RunRequest) -> dict[str, str]:
        run_id, cid, budget = manager.start(
            req.message, req.mode, req.conversation_id, req.model, req.tdd
        )
        return {"run_id": run_id, "conversation_id": cid, "token_budget": str(budget)}

    @app.get("/api/runs/{run_id}/events")
    async def events(run_id: str) -> EventSourceResponse:
        if not manager.exists(run_id):
            raise HTTPException(status_code=404, detail="unknown run")

        async def source() -> AsyncIterator[dict[str, str]]:
            async for event in manager.stream(run_id):
                yield {"data": json.dumps(event)}

        return EventSourceResponse(source())

    @app.post("/api/runs/{run_id}/stop")
    async def stop_run(run_id: str) -> dict[str, bool]:
        return {"stopped": manager.stop(run_id)}

    @app.post("/api/approvals/{request_id}")
    async def approve(request_id: str, req: ApprovalRequest) -> dict[str, bool]:
        return {"resolved": manager.resolve(request_id, req.approved)}

    @app.get("/api/undo")
    async def undo_status() -> dict[str, int]:
        return {"pending": Checkpointer(workspace).pending()}

    @app.post("/api/undo")
    async def undo() -> dict[str, object]:
        cp = Checkpointer(workspace)
        if manager.active_runs():  # a turn may be appending to the journal right now
            return {"undone": None, "pending": cp.pending(), "busy": True}
        desc = cp.undo_last()  # restore the most recent edit; None if nothing to undo
        return {"undone": desc, "pending": cp.pending()}

    @app.get("/", response_class=HTMLResponse)
    async def index() -> str:
        return (_FRONTEND / "index.html").read_text("utf-8")

    return app
