"""Lock in the system prompt's grounding + anti-loop guidance."""

from __future__ import annotations

from lca.core.prompts import SYSTEM_PROMPT, workspace_note


def test_system_prompt_has_core_rules():
    p = SYSTEM_PROMPT.lower()
    assert "execution is truth" in p
    assert "do not create packages" in p  # the live-test anti-loop fix
    assert "i'm not sure" in p
    assert "never invent" in p


def test_system_prompt_has_security_directive():
    p = SYSTEM_PROMPT.lower()
    assert "security" in p
    assert "never hardcode secrets" in p
    assert "environment variable" in p and ".gitignore" in p
    assert "injection" in p  # sql/shell injection guidance


def test_workspace_note_includes_root():
    assert "/proj" in workspace_note("/proj")
