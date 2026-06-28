"""Best-effort desktop notification when a turn completes (Windows toast/balloon).

Fired by `lca ask/chat --notify` so a long run can finish unattended and still ping
you. Detached + hidden so it never blocks or errors the turn; a no-op off Windows.
"""

from __future__ import annotations

import contextlib
import shutil
import subprocess
import sys

_PS_TEMPLATE = (
    "Add-Type -AssemblyName System.Windows.Forms;"
    "$n = New-Object System.Windows.Forms.NotifyIcon;"
    "$n.Icon = [System.Drawing.SystemIcons]::Information;"
    "$n.BalloonTipTitle = {title};"
    "$n.BalloonTipText = {body};"
    "$n.Visible = $true; $n.ShowBalloonTip(5000); Start-Sleep -Seconds 6; $n.Dispose()"
)


def _ps_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def notify(title: str, body: str) -> None:
    """Show a desktop notification. Best-effort: silently does nothing on failure."""
    if sys.platform != "win32":
        return
    powershell = shutil.which("powershell") or shutil.which("pwsh")
    if powershell is None:
        return
    script = _PS_TEMPLATE.format(title=_ps_quote(title), body=_ps_quote(body[:200] or "Done"))
    with contextlib.suppress(OSError):  # fire-and-forget; never block or raise
        subprocess.Popen(
            [powershell, "-NoProfile", "-WindowStyle", "Hidden", "-Command", script],
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
