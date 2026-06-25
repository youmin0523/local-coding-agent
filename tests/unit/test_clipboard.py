"""Clipboard helper degrades gracefully (no real clipboard touched in tests)."""

from __future__ import annotations

import pytest

import lca.cli.clipboard as clip


def test_returns_false_when_no_tool(monkeypatch: pytest.MonkeyPatch):
    # No clipboard executable available on any platform -> False, never raises.
    monkeypatch.setattr(clip.shutil, "which", lambda _name: None)
    assert clip.copy_to_clipboard("hello world") is False
