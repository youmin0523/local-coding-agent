"""Context building: recency trimming + summary of dropped older turns."""

from __future__ import annotations

from pathlib import Path

from lca.core.context import ContextBuilder
from lca.core.messages import Message
from lca.core.session import Session


def test_recent_history_kept_and_old_summarized(tmp_path: Path):
    session = Session(workspace_root=tmp_path, token_budget=200)  # tiny budget
    # many turns; older ones won't fit
    for i in range(8):
        session.add(Message.user(f"task number {i} about widgets and gadgets " + "x" * 50))
        session.add(Message.assistant(f"answer {i} " + "y" * 50))

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
