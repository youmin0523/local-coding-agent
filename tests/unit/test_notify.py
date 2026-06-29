"""Desktop-notification helper: PowerShell-injection-safe quoting + platform gating.

`notify()` interpolates a title/body that originate from agent output or the user
message into a PowerShell command, so the single-quote escaping is a security
boundary, not cosmetics. These tests never actually pop a balloon or touch a real
PowerShell — the platform, `which`, and `Popen` are all monkeypatched.
"""

from __future__ import annotations

import lca.cli.notify as notify_mod
from lca.cli.notify import _ps_quote, notify


def test_ps_quote_neutralizes_injection():
    quoted = _ps_quote("x'; Remove-Item C:\\ -Recurse; '")
    assert quoted.startswith("'") and quoted.endswith("'")
    assert "''" in quoted  # interior single quotes are doubled, not left bare
    # after collapsing the doubled (literal) quotes, no lone string-terminating quote remains
    assert "'" not in quoted[1:-1].replace("''", "")


def test_notify_spawns_hidden_detached_powershell(monkeypatch):
    calls: list[tuple] = []
    monkeypatch.setattr(notify_mod.sys, "platform", "win32")
    monkeypatch.setattr(notify_mod.shutil, "which", lambda _name: "powershell")
    monkeypatch.setattr(notify_mod.subprocess, "Popen", lambda *a, **k: calls.append((a, k)))

    notify("Title", "Body's done")  # apostrophe in the body must not raise

    assert len(calls) == 1
    argv = calls[0][0][0]
    assert "-NoProfile" in argv and "-WindowStyle" in argv and "Hidden" in argv
    assert "Body''s done" in argv[-1]  # body single-quote doubled inside the script


def test_notify_is_noop_off_windows(monkeypatch):
    calls: list[int] = []
    monkeypatch.setattr(notify_mod.sys, "platform", "linux")
    monkeypatch.setattr(notify_mod.subprocess, "Popen", lambda *a, **k: calls.append(1))

    notify("Title", "Body")

    assert calls == []
