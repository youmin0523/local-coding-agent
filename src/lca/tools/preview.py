"""A human-readable preview of what a gated tool call will do.

Shown at approval time so the user reviews the actual change (a diff for writes, the
command for shells) before allowing — not just the raw JSON arguments.
"""

from __future__ import annotations

import difflib
from pathlib import Path

from lca.core.messages import ToolCall

_MAX = 4000


def _diff(old: str, new: str, rel: str) -> str:
    return "".join(
        difflib.unified_diff(
            old.splitlines(keepends=True),
            new.splitlines(keepends=True),
            fromfile=f"a/{rel}",
            tofile=f"b/{rel}",
        )
    )


def preview_call(call: ToolCall, workspace: Path) -> str:
    """A short preview of a tool call's effect, or '' if there's nothing useful to show."""
    args = call.arguments
    if call.name == "write_file":
        rel = str(args.get("path", ""))
        target = workspace / rel
        old = target.read_text("utf-8", errors="replace") if target.is_file() else ""
        out = _diff(old, str(args.get("content", "")), rel) or f"(new file {rel})"
        return out[:_MAX]
    if call.name == "edit_file":
        return f"- {args.get('old_string', '')}\n+ {args.get('new_string', '')}"[:_MAX]
    if call.name in ("run_shell", "run_python", "run_checks"):
        return str(args.get("command") or args.get("code") or args.get("kind") or "")[:_MAX]
    return ""
