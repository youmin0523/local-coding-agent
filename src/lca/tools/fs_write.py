"""Mutating filesystem tools: write_file and edit_file.

Both are `RiskLevel.WRITE`, so under the default GATED policy they require
approval. Each returns a unified-diff artifact so the UI can show exactly what
changed before (or after) the user approves.
"""

from __future__ import annotations

import difflib
from typing import Any

from lca.tools.base import Artifact, RiskLevel, ToolContext, ToolResult, ToolSpec
from lca.tools.checkpoint import Checkpointer
from lca.tools.secret_scan import scan_text
from lca.tools.util import safe_resolve, to_rel


def _secret_warning(content: str) -> str:
    """A loud, non-blocking note if the just-written content holds a hardcoded secret."""
    hits = scan_text(content)
    if not hits:
        return ""
    kinds = ", ".join(sorted({k for _, k in hits}))
    return (
        f"\n⚠ SECURITY: this content looks like it contains a hardcoded secret ({kinds}). "
        "Move it to an environment variable / settings and keep it out of version control."
    )


def _locate(content: str, old: str) -> tuple[int, int] | str:
    """Find a unique span for ``old`` in ``content``: exact first, then whitespace-
    flexible (matching on stripped lines, so indentation/trailing-space drift is OK).

    Returns ``(start, end)`` char offsets, or an error string explaining the miss.
    """
    exact = content.count(old)
    if exact == 1:
        i = content.index(old)
        return (i, i + len(old))
    if exact > 1:
        return f"old_string is not unique ({exact} exact matches); add more surrounding context."

    old_lines = old.splitlines()
    if not old_lines:
        return "old_string not found; read the file and copy an exact snippet."
    stripped_old = [ln.strip() for ln in old_lines]
    file_lines = content.splitlines(keepends=True)
    stripped_file = [ln.strip() for ln in file_lines]
    hits = [
        start
        for start in range(len(file_lines) - len(old_lines) + 1)
        if stripped_file[start : start + len(old_lines)] == stripped_old
    ]
    if len(hits) == 1:
        start = hits[0]
        s_off = sum(len(file_lines[k]) for k in range(start))
        e_off = sum(len(file_lines[k]) for k in range(start + len(old_lines)))
        return (s_off, e_off)
    if len(hits) > 1:
        return f"old_string matches {len(hits)} places (whitespace-insensitive); add more context."
    return "old_string not found; read the file and copy an exact snippet."


def _unified_diff(old: str, new: str, path: str) -> str:
    diff = difflib.unified_diff(
        old.splitlines(keepends=True),
        new.splitlines(keepends=True),
        fromfile=f"a/{path}",
        tofile=f"b/{path}",
    )
    return "".join(diff)


class WriteFileTool:
    spec = ToolSpec(
        name="write_file",
        description="Create or overwrite a workspace file with the given UTF-8 content.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path (relative to workspace)."},
                "content": {"type": "string", "description": "Full new file content."},
            },
            "required": ["path", "content"],
        },
        risk=RiskLevel.WRITE,
    )

    async def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        path = safe_resolve(ctx.workspace_root, str(args["path"]))
        new_content = str(args["content"])
        old_content = path.read_text("utf-8", errors="replace") if path.is_file() else ""
        rel = to_rel(ctx.workspace_root, path)
        Checkpointer(ctx.workspace_root).record(path)  # reversible via `lca undo`
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(new_content, encoding="utf-8")
        diff = _unified_diff(old_content, new_content, rel) or "(new file)"
        action = "overwrote" if old_content else "created"
        return ToolResult.ok_text(
            f"{action} {rel} ({len(new_content)} bytes){_secret_warning(new_content)}",
            artifacts=[Artifact(kind="diff", title=rel, body=diff, uri=rel)],
        )


class EditFileTool:
    spec = ToolSpec(
        name="edit_file",
        description=(
            "Replace a unique snippet in a workspace file. Matches exactly first, then "
            "whitespace-flexibly (indentation/trailing-space drift is tolerated). Fails "
            "with guidance if the snippet is missing or not unique."
        ),
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path (relative to workspace)."},
                "old_string": {"type": "string", "description": "Exact text to replace (unique)."},
                "new_string": {"type": "string", "description": "Replacement text."},
            },
            "required": ["path", "old_string", "new_string"],
        },
        risk=RiskLevel.WRITE,
    )

    async def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        path = safe_resolve(ctx.workspace_root, str(args["path"]))
        if not path.is_file():
            return ToolResult.error(f"not a file: {args['path']}")
        old_string = str(args["old_string"])
        new_string = str(args["new_string"])
        content = path.read_text("utf-8", errors="replace")
        located = _locate(content, old_string)
        if isinstance(located, str):
            return ToolResult.error(located)
        start, end = located
        # Preserve a trailing newline if the matched block had one but the replacement doesn't,
        # so a whitespace-flexible block edit can't accidentally merge the following line.
        if content[start:end].endswith("\n") and not new_string.endswith("\n"):
            new_string += "\n"
        updated = content[:start] + new_string + content[end:]
        rel = to_rel(ctx.workspace_root, path)
        Checkpointer(ctx.workspace_root).record(path)  # reversible via `lca undo`
        path.write_text(updated, encoding="utf-8")
        diff = _unified_diff(content, updated, rel)
        return ToolResult.ok_text(
            f"edited {rel}{_secret_warning(new_string)}",
            artifacts=[Artifact(kind="diff", title=rel, body=diff, uri=rel)],
        )


def write_tools() -> list[Any]:
    return [WriteFileTool(), EditFileTool()]
