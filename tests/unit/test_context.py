"""Context building: recency trimming + summary of dropped older turns."""

from __future__ import annotations

from pathlib import Path

from lca.core.context import _GROUNDING_CHAR_CAP, ContextBuilder, RetrievedContext
from lca.core.messages import Message
from lca.core.session import Session


def test_recent_history_kept_and_old_summarized(tmp_path: Path):
    session = Session(workspace_root=tmp_path, token_budget=600)  # ~2400 char budget
    # many large turns so the oldest exceed the budget and get dropped
    for i in range(12):
        session.add(Message.user(f"task number {i} about widgets and gadgets " + "x" * 300))
        session.add(Message.assistant(f"answer {i} " + "y" * 300))

    messages = ContextBuilder().build(session, "what now?")
    system = messages[0].content or ""
    # the most recent user turn is preserved verbatim; the last message is the new input
    assert messages[-1].content == "what now?"
    # older turns are summarized, not silently lost
    assert "Earlier in this session" in system
    assert "task number" in system


def test_no_summary_when_everything_fits(tmp_path: Path):
    session = Session(workspace_root=tmp_path, token_budget=16384)
    session.add(Message.user("only task"))
    session.add(Message.assistant("done"))
    system = ContextBuilder().build(session, "next")[0].content or ""
    assert "Earlier in this session" not in system


def test_grounding_block_is_capped(tmp_path: Path):
    session = Session(workspace_root=tmp_path, token_budget=16384)
    huge = RetrievedContext(code_snippets=["x" * (_GROUNDING_CHAR_CAP + 5000)])
    system = ContextBuilder().build(session, "q", huge)[0].content or ""
    assert "[grounding truncated]" in system


def test_language_note_injected(tmp_path: Path):
    session = Session(workspace_root=tmp_path, token_budget=16384)
    system = ContextBuilder(language="Korean").build(session, "hi")[0].content or ""
    assert "Always respond in Korean" in system
    # default builder (no language) stays language-neutral
    neutral = ContextBuilder().build(session, "hi")[0].content or ""
    assert "LANGUAGE:" not in neutral


def test_tdd_directive_injected_only_when_enabled(tmp_path: Path):
    on = Session(workspace_root=tmp_path, token_budget=16384, tdd=True)
    system = ContextBuilder().build(on, "add a parser")[0].content or ""
    assert "TDD MODE" in system and "CONFIRM IT FAILS" in system
    # default session (tdd off) carries no test-first directive
    off = Session(workspace_root=tmp_path, token_budget=16384)
    assert "TDD MODE" not in (ContextBuilder().build(off, "add a parser")[0].content or "")
