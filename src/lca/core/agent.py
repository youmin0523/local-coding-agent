"""The ReAct agent loop — the orchestration heart of lca.

`Agent.run_turn` is an async generator that yields `AgentEvent`s. Per iteration it:
build context → call the model (streaming tokens live) → parse tool calls → check
permissions (approve / deny / ask) → execute in the sandbox → feed observations
back → repeat until the model answers with no tool call or a hard cap trips.

It depends only on interfaces (`LLMProvider`, `ToolRegistry`, `PermissionPolicy`,
`Approver`), so the same loop runs identically behind the CLI, the web UI, and the
`FakeProvider` in tests. Verification, memory, and routing hook in here in later
milestones; this milestone is the clean, well-guarded core loop.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

from lca.core.context import ContextBuilder, RetrievedContext
from lca.core.errors import ProviderError, ToolNotFoundError
from lca.core.events import (
    Abstained,
    AgentEvent,
    ApprovalRequired,
    ApprovalResolved,
    ErrorEvent,
    TokenDelta,
    ToolFinished,
    ToolProposed,
    ToolStarted,
    TurnFinished,
    VerificationResult,
)
from lca.core.messages import Message, ToolCall
from lca.core.session import Session
from lca.observability.logging import get_logger
from lca.permissions.approver import Approver
from lca.permissions.policy import Decision, PermissionPolicy
from lca.permissions.sandbox import SandboxRunner
from lca.providers.base import ChatRequest, LLMProvider, ToolSchema
from lca.tools.base import ToolContext, ToolResult, ToolSpec
from lca.tools.registry import ToolRegistry

if TYPE_CHECKING:
    from lca.memory.memory import Memory
    from lca.rag.retriever import Retriever
    from lca.verification.gate import Verifier

log = get_logger("core.agent")


class Agent:
    def __init__(
        self,
        provider: LLMProvider,
        registry: ToolRegistry,
        policy: PermissionPolicy,
        approver: Approver,
        *,
        model: str,
        retriever: Retriever | None = None,
        verifier: Verifier | None = None,
        memory: Memory | None = None,
        max_tool_iterations: int = 8,
        temperature: float = 0.2,
        max_tokens: int = 2048,
        sandbox_timeout_s: float = 120.0,
        no_network: bool = False,
    ) -> None:
        self._provider = provider
        self._registry = registry
        self._policy = policy
        self._approver = approver
        self._model = model
        self._retriever = retriever
        self._verifier = verifier
        self._memory = memory
        self._max_iter = max_tool_iterations
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._sandbox_timeout = sandbox_timeout_s
        self._no_network = no_network
        self._builder = ContextBuilder()

    async def run_turn(self, session: Session, user_input: str) -> AsyncIterator[AgentEvent]:
        retrieved = await self._retrieve(user_input)
        messages = self._builder.build(session, user_input, retrieved)
        session.add(Message.user(user_input))
        schemas = self._tool_schemas()
        sandbox = SandboxRunner(
            session.workspace_root,
            timeout_s=self._sandbox_timeout,
            no_network=self._no_network,
        )

        for _ in range(self._max_iter):
            req = ChatRequest(
                messages=messages,
                model=self._model,
                tools=schemas,
                temperature=self._temperature,
                max_tokens=self._max_tokens,
            )
            text_parts: list[str] = []
            calls: list[ToolCall] = []
            try:
                async for chunk in self._provider.chat_stream(req):
                    if chunk.delta_text:
                        text_parts.append(chunk.delta_text)
                        yield TokenDelta(text=chunk.delta_text)
                    if chunk.tool_call is not None:
                        calls.append(chunk.tool_call)
            except ProviderError as exc:
                log.error("agent.provider_error", error=str(exc))
                yield ErrorEvent(message=str(exc), recoverable=False)
                yield TurnFinished(stop_reason="error")
                return

            text = "".join(text_parts)
            assistant = Message.assistant(content=text or None, tool_calls=calls)
            session.add(assistant)
            messages.append(assistant)

            if not calls:
                async for ev in self._finalize(user_input, text):
                    yield ev
                return

            for call in calls:
                async for ev in self._handle_call(call, session, sandbox, messages):
                    yield ev

        yield TurnFinished(stop_reason="budget", content="Stopped: tool-iteration limit reached.")

    async def _finalize(self, task: str, answer: str) -> AsyncIterator[AgentEvent]:
        """Run the verification gate on the final answer; deliver or abstain."""
        if self._verifier is None or not answer.strip():
            yield TurnFinished(stop_reason="complete", content=answer)
            return
        try:
            verdict = await self._verifier.verify_answer(task, answer)
        except Exception as exc:  # verification must never crash a turn
            log.warning("agent.verify_failed", error=str(exc))
            yield TurnFinished(stop_reason="complete", content=answer)
            return
        if verdict is None:
            yield TurnFinished(stop_reason="complete", content=answer)
            return

        yield VerificationResult(
            verdict=verdict.verdict, confidence=verdict.confidence, detail=verdict.rationale
        )
        if verdict.verdict == "pass":
            if self._memory is not None:
                try:
                    await self._memory.remember(task, answer, verified=True)
                except Exception as exc:  # remembering must never break a turn
                    log.warning("agent.remember_failed", error=str(exc))
            yield TurnFinished(stop_reason="complete", content=answer)
            return
        reason = (
            "Verification was not confident enough to assert this answer."
            if verdict.verdict == "uncertain"
            else "Verification found problems with this answer."
        )
        yield Abstained(reason=reason, options=verdict.signals)
        yield TurnFinished(stop_reason="abstained", content=answer)

    async def _handle_call(
        self,
        call: ToolCall,
        session: Session,
        sandbox: SandboxRunner,
        messages: list[Message],
    ) -> AsyncIterator[AgentEvent]:
        try:
            tool = self._registry.get(call.name)
        except ToolNotFoundError:
            available = ", ".join(self._registry.names())
            self._feed(
                messages, session, call, f"No such tool '{call.name}'. Available: {available}"
            )
            return

        spec: ToolSpec = tool.spec
        yield ToolProposed(call=call, risk=spec.risk)

        decision = self._policy.evaluate(call, spec.risk, session.mode, session.allow_cache)
        if decision == Decision.ASK:
            yield ApprovalRequired(request_id=call.id, call=call, risk=spec.risk)
            approved = await self._approver.request(call, spec.risk)
            yield ApprovalResolved(request_id=call.id, approved=approved)
            if not approved:
                decision = Decision.DENY

        if decision == Decision.DENY:
            self._feed(
                messages,
                session,
                call,
                "Permission denied for this action; do not retry it. Consider an alternative.",
            )
            return

        yield ToolStarted(call_id=call.id, name=call.name)
        ctx = ToolContext(
            workspace_root=session.workspace_root,
            approver=self._approver,
            session=session,
            sandbox=sandbox,
        )
        try:
            result = await tool.run(call.arguments, ctx)
        except Exception as exc:  # tools must never crash the loop
            log.exception("agent.tool_error", tool=call.name)
            result = ToolResult.error(f"tool raised {type(exc).__name__}: {exc}")
        yield ToolFinished(call_id=call.id, name=call.name, result=result)
        self._feed(messages, session, call, result.content or ("ok" if result.ok else "failed"))

    @staticmethod
    def _feed(messages: list[Message], session: Session, call: ToolCall, content: str) -> None:
        msg = Message.tool_result(call.id, content, name=call.name)
        messages.append(msg)
        session.add(msg)

    def _tool_schemas(self) -> list[ToolSchema]:
        return [
            ToolSchema(name=s.name, description=s.description, parameters=s.parameters)
            for s in self._registry.specs()
        ]

    async def _retrieve(self, query: str) -> RetrievedContext | None:
        snippets: list[str] = []
        experiences: list[str] = []
        if self._retriever is not None:
            try:
                chunks = await self._retriever.retrieve(query)
                snippets = [c.render() for c in chunks]
            except Exception as exc:  # retrieval failures must not break a turn
                log.warning("agent.retrieve_failed", error=str(exc))
        if self._memory is not None:
            try:
                experiences = await self._memory.recall(query)
            except Exception as exc:
                log.warning("agent.recall_failed", error=str(exc))
        if not snippets and not experiences:
            return None
        return RetrievedContext(code_snippets=snippets, experiences=experiences)
