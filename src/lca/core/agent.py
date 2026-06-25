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
from lca.observability.metrics import Metrics, MetricsSnapshot
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


class _Signals:
    """Per-turn grounding signals used to decide automatic learning.

    ``truth_ok`` is set when an execution-oracle tool (run_checks) passed;
    ``cited`` is set when a tool produced a citation (web fetch/search). Either
    means the answer is grounded enough to learn from without an LLM judge.
    """

    __slots__ = ("checks_failed", "cited", "executed_ok", "truth_ok")

    def __init__(self) -> None:
        self.truth_ok = False  # run_checks (tests/types/lint) passed
        self.checks_failed = False  # run_checks ran and FAILED
        self.executed_ok = False  # code/command ran successfully (run_python/run_shell)
        self.cited = False  # a web citation was produced

    @property
    def grounded(self) -> bool:
        return self.truth_ok or self.executed_ok or self.cited

    @property
    def execution_passed(self) -> bool | None:
        """Tri-state execution signal for verification: failure dominates."""
        if self.checks_failed:
            return False
        if self.truth_ok:
            return True
        return None


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
        samples: int = 1,
        max_tool_iterations: int = 8,
        temperature: float = 0.2,
        max_tokens: int = 2048,
        sandbox_timeout_s: float = 120.0,
        no_network: bool = False,
        skills_note: str = "",
    ) -> None:
        self._provider = provider
        self._registry = registry
        self._policy = policy
        self._approver = approver
        self._model = model
        self._retriever = retriever
        self._verifier = verifier
        self._memory = memory
        self._samples = max(1, samples)
        self._max_iter = max_tool_iterations
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._sandbox_timeout = sandbox_timeout_s
        self._no_network = no_network
        self._builder = ContextBuilder(skills_note=skills_note)
        self._metrics = Metrics()

    @property
    def registry(self) -> ToolRegistry:
        """The tool registry, so callers can register MCP tools before a turn."""
        return self._registry

    def metrics_snapshot(self) -> MetricsSnapshot:
        """Session-cumulative metrics (tool calls/failures, approvals, verdicts)."""
        return self._metrics.snapshot()

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
        signals = _Signals()
        self._metrics.incr("turns")

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
                # base_messages = everything except the just-appended final answer,
                # so best-of-N can resample alternative answers from the same context.
                async for ev in self._finalize(user_input, text, signals, messages[:-1]):
                    yield ev
                return

            for call in calls:
                async for ev in self._handle_call(call, session, sandbox, messages, signals):
                    yield ev

        yield TurnFinished(stop_reason="budget", content="Stopped: tool-iteration limit reached.")

    async def _finalize(
        self, task: str, answer: str, signals: _Signals, base_messages: list[Message]
    ) -> AsyncIterator[AgentEvent]:
        """Verify the final answer (best-of-N), deliver-or-abstain, and learn."""
        if not answer.strip():
            yield TurnFinished(stop_reason="complete", content=answer)
            return

        # Strong path: a verifier is attached. With samples>1 this becomes best-of-N —
        # sample several candidate answers and deliver the best-verified one.
        if self._verifier is not None:
            candidates = [answer]
            if self._samples > 1:
                candidates += await self._sample_candidates(base_messages, self._samples - 1)
            async for ev in self._select_verified(task, candidates, signals.execution_passed):
                yield ev
            return

        # Continuous-learning path: no judge, but the turn was grounded by execution
        # or citations — trustworthy enough to remember automatically.
        if self._memory is not None and signals.grounded:
            source = (
                "passing checks"
                if signals.truth_ok
                else "executed code"
                if signals.executed_ok
                else "cited sources"
            )
            yield VerificationResult(verdict="pass", confidence=0.7, detail=f"grounded by {source}")
            await self._remember(task, answer)
        yield TurnFinished(stop_reason="complete", content=answer)

    async def _select_verified(
        self, task: str, candidates: list[str], execution_passed: bool | None = None
    ) -> AsyncIterator[AgentEvent]:
        """Verify each candidate; deliver the best `pass`, else abstain (best-of-N).

        ``execution_passed`` carries the turn's run_checks result into the verdict so
        execution dominates the judges (a failing check can't be argued into a pass).
        """
        assert self._verifier is not None
        scored: list[tuple[float, str, str, list[str]]] = []  # (conf, verdict, answer, signals)
        for cand in candidates:
            try:
                verdict = await self._verifier.verify_answer(
                    task, cand, execution_passed=execution_passed
                )
            except Exception as exc:  # verification must never crash a turn
                log.warning("agent.verify_failed", error=str(exc))
                yield TurnFinished(stop_reason="complete", content=candidates[0])
                return
            if verdict is None:
                yield TurnFinished(stop_reason="complete", content=cand)
                return
            scored.append((verdict.confidence, verdict.verdict, cand, verdict.signals))

        passing = [s for s in scored if s[1] == "pass"]
        if passing:
            self._metrics.incr("verified_pass")
            conf, _, chosen, _ = max(passing, key=lambda s: s[0])
            detail = f"best of {len(candidates)}" if len(candidates) > 1 else ""
            yield VerificationResult(verdict="pass", confidence=conf, detail=detail)
            await self._remember(task, chosen)
            yield TurnFinished(stop_reason="complete", content=chosen)
            return

        best = max(scored, key=lambda s: s[0])
        conf, verdict_kind, answer, sigs = best
        yield VerificationResult(
            verdict=verdict_kind, confidence=conf, detail=f"of {len(candidates)}"
        )
        reason = (
            "Verification was not confident enough to assert this answer."
            if verdict_kind == "uncertain"
            else "Verification found problems with this answer."
        )
        self._metrics.incr("abstained")
        if self._memory is not None:  # learn from the failure (ReasoningBank caution)
            try:
                await self._memory.note_caution(task, "; ".join(sigs[:2]) or reason)
            except Exception as exc:
                log.warning("agent.caution_failed", error=str(exc))
        yield Abstained(reason=reason, options=sigs)
        yield TurnFinished(stop_reason="abstained", content=answer)

    async def _sample_candidates(self, base_messages: list[Message], n: int) -> list[str]:
        """Sample N alternative final answers (no tools, higher temperature)."""
        out: list[str] = []
        for _ in range(n):
            try:
                text = await self._complete(base_messages, temperature=0.7)
            except ProviderError as exc:
                log.warning("agent.sample_failed", error=str(exc))
                break
            if text.strip():
                out.append(text)
        return out

    async def _complete(self, messages: list[Message], *, temperature: float) -> str:
        req = ChatRequest(
            messages=messages,
            model=self._model,
            tools=[],
            temperature=temperature,
            max_tokens=self._max_tokens,
        )
        parts: list[str] = []
        async for chunk in self._provider.chat_stream(req):
            if chunk.delta_text:
                parts.append(chunk.delta_text)
        return "".join(parts)

    async def _remember(self, task: str, answer: str) -> None:
        if self._memory is None:
            return
        try:
            await self._memory.remember(task, answer, verified=True)
        except Exception as exc:  # remembering must never break a turn
            log.warning("agent.remember_failed", error=str(exc))

    async def _handle_call(
        self,
        call: ToolCall,
        session: Session,
        sandbox: SandboxRunner,
        messages: list[Message],
        signals: _Signals,
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
            self._metrics.incr("approvals_requested")
            yield ApprovalRequired(request_id=call.id, call=call, risk=spec.risk)
            approved = await self._approver.request(call, spec.risk)
            yield ApprovalResolved(request_id=call.id, approved=approved)
            if not approved:
                self._metrics.incr("denied")
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
        self._metrics.incr("tool_calls")
        if not result.ok:
            self._metrics.incr("tool_failures")
        if result.is_truth and not result.ok:
            signals.checks_failed = True  # run_checks ran and failed: execution truth = fail
        if result.ok:
            if result.is_truth:
                signals.truth_ok = True  # run_checks passed: strongest signal
            if call.name in ("run_python", "run_shell"):
                signals.executed_ok = True
        if any(a.kind == "citation" for a in result.artifacts):
            signals.cited = True
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
