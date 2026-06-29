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

import re
from collections.abc import AsyncIterator
from pathlib import Path
from typing import TYPE_CHECKING

from lca.core.context import ContextBuilder, RetrievedContext
from lca.core.errors import ProviderError, ToolNotFoundError
from lca.core.events import (
    Abstained,
    AgentEvent,
    ApprovalRequired,
    ApprovalResolved,
    ContextRecalled,
    ErrorEvent,
    FilesChanged,
    RunConfig,
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
from lca.permissions.approver import Approver, AutoApprover
from lca.permissions.modes import AutonomyMode
from lca.permissions.policy import Decision, PermissionPolicy
from lca.permissions.sandbox import SandboxRunner
from lca.providers.base import ChatRequest, LLMProvider, ToolSchema
from lca.tools.base import ToolContext, ToolResult, ToolSpec
from lca.tools.preview import preview_call
from lca.tools.registry import ToolRegistry

if TYPE_CHECKING:
    from lca.memory.memory import Memory
    from lca.rag.retriever import Retriever
    from lca.verification.gate import Verifier

log = get_logger("core.agent")

# How many times to nudge-and-retry when the model returns an empty completion.
_MAX_EMPTY_RETRIES = 2
# `@path/to/file` mentions in the user's message → inject that file as explicit context.
_MENTION_RE = re.compile(r"@([\w./\\-]+)")
_MENTION_MAX_CHARS = 4000
# Delegation is depth-1 only: a sub-agent cannot spawn its own sub-agents (no recursion).
_MAX_SUBAGENT_DEPTH = 1
# A sub-agent gets a smaller tool-iteration budget than the parent — focused, not open-ended.
_SUBAGENT_MAX_ITER = 6
# Before delivering, the agent must run code it wrote. Nudge once if it tries to finish
# with unexecuted code; bounded so a model that can't run it still terminates.
_MAX_CODE_NUDGES = 1
_CODE_EXTS = (".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java", ".rb", ".c", ".cpp")


class _Signals:
    """Per-turn grounding signals used to decide automatic learning.

    ``truth_ok`` is set when an execution-oracle tool (run_checks) passed;
    ``cited`` is set when a tool produced a citation (web fetch/search). Either
    means the answer is grounded enough to learn from without an LLM judge.
    """

    __slots__ = ("changed_files", "checks_failed", "cited", "executed_ok", "truth_ok")

    def __init__(self) -> None:
        self.truth_ok = False  # run_checks (tests/types/lint) passed
        self.checks_failed = False  # run_checks ran and FAILED
        self.executed_ok = False  # code/command ran successfully (run_python/run_shell)
        self.cited = False  # a web citation was produced
        self.changed_files: list[str] = []  # files this turn created/edited (de-duped, ordered)

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
        response_language: str = "",
        subagent_depth: int = 0,
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
        self._subagent_depth = subagent_depth
        self._builder = ContextBuilder(skills_note=skills_note, language=response_language)
        self._metrics = Metrics()

    @property
    def registry(self) -> ToolRegistry:
        """The tool registry, so callers can register MCP tools before a turn."""
        return self._registry

    def metrics_snapshot(self) -> MetricsSnapshot:
        """Session-cumulative metrics (tool calls/failures, approvals, verdicts)."""
        return self._metrics.snapshot()

    async def run_turn(self, session: Session, user_input: str) -> AsyncIterator[AgentEvent]:
        yield RunConfig(model=self._model, verify=self._verifier is not None, samples=self._samples)
        retrieved = await self._retrieve(user_input)
        mentions = self._mentioned_files(user_input, session.workspace_root)
        if mentions:
            retrieved = retrieved or RetrievedContext()
            retrieved.code_snippets = mentions + retrieved.code_snippets
        messages = self._builder.build(session, user_input, retrieved)
        session.add(Message.user(user_input))
        if retrieved and (retrieved.experiences or retrieved.code_snippets):
            n_exp, n_snip = len(retrieved.experiences), len(retrieved.code_snippets)
            bits = []
            if n_exp:
                bits.append(f"{n_exp} verified solution(s) reused")
            if n_snip:
                bits.append(f"{n_snip} code snippet(s)")
            yield ContextRecalled(experiences=n_exp, snippets=n_snip, detail=", ".join(bits))
        schemas = self._tool_schemas()
        sandbox = SandboxRunner(
            session.workspace_root,
            timeout_s=self._sandbox_timeout,
            no_network=self._no_network,
        )
        signals = _Signals()
        self._metrics.incr("turns")
        empty_retries = 0
        code_nudges = 0
        temperature = self._temperature

        for _ in range(self._max_iter):
            req = ChatRequest(
                messages=messages,
                model=self._model,
                tools=schemas,
                temperature=temperature,
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

            # Degenerate turn: the model returned neither prose nor a tool call.
            # Small models occasionally emit an empty completion — nudge and retry
            # (with a small temperature bump) before giving up, rather than silently
            # delivering nothing.
            if not calls and not text.strip():
                if empty_retries < _MAX_EMPTY_RETRIES:
                    empty_retries += 1
                    temperature = min(0.8, temperature + 0.3)
                    self._metrics.incr("empty_completions")
                    log.warning("agent.empty_completion", attempt=empty_retries)
                    messages.append(
                        Message.user(
                            "Your previous response was empty. Answer the request now, "
                            "directly and concisely."
                        )
                    )
                    continue
                yield TurnFinished(
                    stop_reason="empty",
                    content="I couldn't produce a response. Please rephrase or add detail.",
                )
                return

            assistant = Message.assistant(content=text or None, tool_calls=calls)
            session.add(assistant)
            messages.append(assistant)

            if not calls:
                # Gate delivery on execution: if the model wrote code but never ran it,
                # nudge it to actually run/simulate the code before finishing (once).
                if self._has_unrun_code(signals) and code_nudges < _MAX_CODE_NUDGES:
                    code_nudges += 1
                    self._metrics.incr("code_exec_nudges")
                    messages.append(
                        Message.user(
                            "You wrote or edited code but have not run it. Before finishing, "
                            "actually execute it — run_checks, or run_python that imports/calls "
                            "what you wrote with a known expected result — and confirm it works. "
                            "If it is already verified, run it once more to show the output."
                        )
                    )
                    continue
                if signals.changed_files:
                    yield FilesChanged(paths=list(signals.changed_files))
                # base_messages = everything except the just-appended final answer,
                # so best-of-N can resample alternative answers from the same context.
                async for ev in self._finalize(user_input, text, signals, messages[:-1]):
                    yield ev
                return

            for call in calls:
                async for ev in self._handle_call(call, session, sandbox, messages, signals):
                    yield ev

        if signals.changed_files:
            yield FilesChanged(paths=list(signals.changed_files))
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
            async for ev in self._select_verified(
                task, candidates, signals.execution_passed, base_messages
            ):
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
        self,
        task: str,
        candidates: list[str],
        execution_passed: bool | None = None,
        base_messages: list[Message] | None = None,
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
            except Exception as exc:  # verifier infra failed — deliver, but never as "verified"
                log.warning("agent.verify_failed", error=str(exc))
                grounded = execution_passed is True
                yield VerificationResult(
                    verdict="pass" if grounded else "uncertain",
                    confidence=0.6 if grounded else 0.0,
                    detail="grounded by execution (judge unavailable)"
                    if grounded
                    else "unverified — the verifier errored",
                )
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
        # No candidate passed. Before abstaining, try ONE self-repair from the failure
        # signals and re-verify it — this recovers correct answers the judges were merely
        # unsure about (the gate's main false-negative source) without lowering the bar.
        # Skipped when execution already proved the answer wrong (a text fix won't change it).
        if base_messages is not None and execution_passed is not False:
            repaired = await self._repair(base_messages, best[2], best[3])
            if repaired.strip() and repaired.strip() != best[2].strip():
                try:
                    v = await self._verifier.verify_answer(
                        task, repaired, execution_passed=execution_passed
                    )
                except Exception as exc:
                    log.warning("agent.repair_verify_failed", error=str(exc))
                    v = None
                if v is not None and v.verdict == "pass":
                    self._metrics.incr("verified_pass")
                    self._metrics.incr("self_repaired")
                    yield VerificationResult(
                        verdict="pass", confidence=v.confidence, detail="after self-repair"
                    )
                    await self._remember(task, repaired)
                    yield TurnFinished(stop_reason="complete", content=repaired)
                    return

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

    async def _repair(self, base_messages: list[Message], draft: str, signals: list[str]) -> str:
        """One best-effort fix of a draft that failed verification, using its signals.

        Best-effort: any failure returns "" so the caller falls through to abstaining.
        """
        critique = "; ".join(signals[:3]) or "the answer was not convincing"
        repair_msgs = [
            *base_messages,
            Message.assistant(content=draft),
            Message.user(
                f"That answer did not pass verification ({critique}). Give a corrected, "
                "complete answer that fixes those issues. Reply with the answer only."
            ),
        ]
        try:
            return await self._complete(repair_msgs, temperature=0.3)
        except Exception as exc:  # repair must never break the turn → abstain instead
            log.warning("agent.repair_failed", error=str(exc))
            return ""

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
            preview = preview_call(call, session.workspace_root)  # diff/command to review
            yield ApprovalRequired(request_id=call.id, call=call, risk=spec.risk, preview=preview)
            approved = await self._approver.request(call, spec.risk, preview)
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
        if self._subagent_depth < _MAX_SUBAGENT_DEPTH:  # top-level only → no recursion
            ctx.extra["subagent"] = self._run_subagent
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
            if call.name in ("write_file", "edit_file"):
                path = str(call.arguments.get("path", "")).strip()
                if path and path not in signals.changed_files:
                    signals.changed_files.append(path)
        if any(a.kind == "citation" for a in result.artifacts):
            signals.cited = True
        self._feed(messages, session, call, result.content or ("ok" if result.ok else "failed"))

    async def _run_subagent(self, task: str, parent: Session) -> tuple[str, str]:
        """Run a focused subtask in a fresh, depth-bounded sub-agent.

        Returns ``(stop_reason, content)`` so the caller can tell a clean completion from
        an abstain / budget-stop / empty turn instead of folding failure text back as if it
        were the answer. Shares this agent's provider, tools, and workspace, but gets a clean
        session and a smaller iteration budget. The spawn was already gated (delegate = WRITE
        risk), so the sub-agent runs autonomously — its edits are checkpointed and reversible.
        """
        child = Agent(
            self._provider,
            self._registry,
            self._policy,
            AutoApprover(),
            model=self._model,
            max_tool_iterations=min(self._max_iter, _SUBAGENT_MAX_ITER),
            temperature=self._temperature,
            max_tokens=self._max_tokens,
            sandbox_timeout_s=self._sandbox_timeout,
            no_network=self._no_network,
            subagent_depth=self._subagent_depth + 1,
        )
        child_session = Session(
            workspace_root=parent.workspace_root,
            mode=AutonomyMode.AUTONOMOUS,
            token_budget=parent.token_budget,
        )
        stop_reason, answer = "complete", ""
        async for ev in child.run_turn(child_session, task):
            if isinstance(ev, TurnFinished):
                stop_reason, answer = ev.stop_reason, ev.content
        return stop_reason, answer

    @staticmethod
    def _has_unrun_code(signals: _Signals) -> bool:
        """True if the turn wrote a code file but never executed anything to verify it."""
        if signals.truth_ok or signals.executed_ok:
            return False
        return any(p.strip().endswith(_CODE_EXTS) for p in signals.changed_files)

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

    def _mentioned_files(self, text: str, workspace: Path) -> list[str]:
        """Read files the user referenced with `@path` and return them as context snippets."""
        root = workspace.resolve()
        out: list[str] = []
        for rel in dict.fromkeys(_MENTION_RE.findall(text)):  # de-duped, order-preserving
            try:
                path = (root / rel).resolve()
                path.relative_to(root)  # stay inside the workspace
            except (ValueError, OSError):
                continue
            if path.is_file():
                try:
                    body = path.read_text("utf-8", errors="replace")[:_MENTION_MAX_CHARS]
                except OSError:
                    continue
                out.append(f"# {rel} (referenced by the user)\n{body}")
        return out

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
