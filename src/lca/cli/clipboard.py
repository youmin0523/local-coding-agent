"""Copy text to the system clipboard, cross-platform, UTF-8 safe.

Used by `lca ask --copy` so an answer can be pasted in one go. Best-effort: returns
False (never raises) if no clipboard mechanism is available, so the CLI can fall
back to printing / `--md`.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def copy_to_clipboard(text: str) -> bool:
    """Put ``text`` on the clipboard. Returns True on success, False otherwise."""
    if sys.platform == "win32":
        return _copy_windows(text)
    candidates = (
        [["pbcopy"]]
        if sys.platform == "darwin"
        else [["wl-copy"], ["xclip", "-selection", "clipboard"], ["xsel", "--clipboard", "--input"]]
    )
    for cmd in candidates:
        exe = shutil.which(cmd[0])
        if exe is None:
            continue
        try:
            subprocess.run([exe, *cmd[1:]], input=text.encode("utf-8"), check=True)
            return True
        except (OSError, subprocess.SubprocessError):
            continue
    return False


def _copy_windows(text: str) -> bool:
    """Use PowerShell Set-Clipboard via a UTF-8 temp file (handles Korean/Unicode)."""
    powershell = shutil.which("powershell") or shutil.which("pwsh")
    if powershell is None:
        return False
    tmp: Path | None = None
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".txt", encoding="utf-8", delete=False) as fh:
            fh.write(text)
            tmp = Path(fh.name)
        subprocess.run(
            [
                powershell,
                "-NoProfile",
                "-Command",
                f"Get-Content -Raw -Encoding utf8 -LiteralPath '{tmp}' | Set-Clipboard",
            ],
            check=True,
        )
        return True
    except (OSError, subprocess.SubprocessError):
        return False
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)
