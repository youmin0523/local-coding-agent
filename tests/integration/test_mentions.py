"""@-mentions: a `@path` in the user's message injects that file as context."""

from __future__ import annotations

from pathlib import Path

from helpers import drain
from lca.core.agent import Agent
from lca.core.session import Session
from lca.permissions.approver import AutoApprover
from lca.permissions.policy import DefaultPolicy
from lca.providers.fake import FakeProvider, text_chunks
from lca.tools import build_default_registry


def _agent(provider: FakeProvider) -> Agent:
    return Agent(
        provider,
        build_default_registry(enable_web=False),
        DefaultPolicy(),
        AutoApprover(),
        model="fake",
    )


def test_mentioned_file_is_read_into_context(workspace: Path):
    (workspace / "target.py").write_text("SECRET_MARKER = 1234\n", "utf-8")
    agent = _agent(FakeProvider([text_chunks("done")]))
    snippets = agent._mentioned_files("please review @target.py", workspace)
    assert any("SECRET_MARKER = 1234" in s and "target.py" in s for s in snippets)


def test_mention_ignores_nonexistent_and_escapes(workspace: Path):
    agent = _agent(FakeProvider([text_chunks("ok")]))
    # non-existent file and a traversal attempt → no snippets, no crash
    assert agent._mentioned_files("@nope.py and @../../etc/passwd", workspace) == []


async def test_mention_reaches_the_prompt(workspace: Path):
    (workspace / "m.py").write_text("MENTION_TOKEN = 'xyz'\n", "utf-8")
    provider = FakeProvider([text_chunks("acknowledged")])
    agent = _agent(provider)
    session = Session(workspace_root=workspace)
    await drain(agent.run_turn(session, "explain @m.py"))
    # the system prompt the model received should contain the mentioned file
    system = provider.requests[0].messages[0].content or ""
    assert "MENTION_TOKEN" in system
