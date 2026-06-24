"""Mutating filesystem tools: write_file and edit_file.

Both are `RiskLevel.WRITE`, so under the default GATED policy they require
approval. Each returns a unified-diff artifact so the UI can show exactly what
changed before (or after) the user approves.
"""

from __future__ import annotations

import difflib
from typing import Any

from lca.tools.base import Artifact, RiskLevel, ToolContext, ToolResult, ToolSpec
from lca.tools.util import safe_resolve, to_rel


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
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(new_content, encoding="utf-8")
        diff = _unified_diff(old_content, new_content, rel) or "(new file)"
        action = "overwrote" if old_content else "created"
        return ToolResult.ok_text(
            f"{action} {rel} ({len(new_content)} bytes)",
            artifacts=[Artifact(kind="diff", title=rel, body=diff, uri=rel)],
        )


class EditFileTool:
    spec = ToolSpec(
        name="edit_file",
        description=(
            "Replace an exact, unique substring in a workspace file. Fails if the "
            "old_string is missing or not unique."
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
        count = content.count(old_string)
        if count == 0:
            return ToolResult.error("old_string not found; read the file and copy it exactly.")
        if count > 1:
            return ToolResult.error(
                f"old_string is not unique ({count} matches); add more context."
            )
        updated = content.replace(old_string, new_string, 1)
        rel = to_rel(ctx.workspace_root, path)
        path.write_text(updated, encoding="utf-8")
        diff = _unified_diff(content, updated, rel)
        return ToolResult.ok_text(
            f"edited {rel}",
            artifacts=[Artifact(kind="diff", title=rel, body=diff, uri=rel)],
        )


def write_tools() -> list[Any]:
    return [WriteFileTool(), EditFileTool()]
