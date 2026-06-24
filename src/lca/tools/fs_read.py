"""Read-only filesystem tools: read_file, list_dir, glob, grep.

All are `RiskLevel.READ`, so they run without approval. Every path is confined to
the workspace via `safe_resolve`. These give the agent the grounding it needs to
answer about real code instead of guessing.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from lca.tools.base import RiskLevel, ToolContext, ToolResult, ToolSpec
from lca.tools.util import safe_resolve, to_rel

_MAX_FILE_BYTES = 100_000
_MAX_MATCHES = 200


class ReadFileTool:
    spec = ToolSpec(
        name="read_file",
        description="Read a UTF-8 text file from the workspace and return its contents.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path (relative to workspace)."},
            },
            "required": ["path"],
        },
        risk=RiskLevel.READ,
    )

    async def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        path = safe_resolve(ctx.workspace_root, str(args["path"]))
        if not path.is_file():
            return ToolResult.error(f"not a file: {args['path']}")
        data = path.read_bytes()[:_MAX_FILE_BYTES]
        text = data.decode("utf-8", errors="replace")
        suffix = "" if len(text) < _MAX_FILE_BYTES else "\n…[truncated]"
        return ToolResult.ok_text(f"{to_rel(ctx.workspace_root, path)}:\n{text}{suffix}")


class ListDirTool:
    spec = ToolSpec(
        name="list_dir",
        description="List the entries of a directory in the workspace.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Directory path; defaults to root."},
            },
        },
        risk=RiskLevel.READ,
    )

    async def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        target = safe_resolve(ctx.workspace_root, str(args.get("path", ".")))
        if not target.is_dir():
            return ToolResult.error(f"not a directory: {args.get('path', '.')}")
        entries = sorted(target.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
        lines = [f"{'📄' if p.is_file() else '📁'} {p.name}" for p in entries]
        return ToolResult.ok_text("\n".join(lines) or "(empty)")


class GlobTool:
    spec = ToolSpec(
        name="glob",
        description="Find files in the workspace matching a glob pattern (e.g. '**/*.py').",
        parameters={
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Glob pattern."},
            },
            "required": ["pattern"],
        },
        risk=RiskLevel.READ,
    )

    async def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        root = ctx.workspace_root.resolve()
        matches = [to_rel(root, p) for p in sorted(root.glob(str(args["pattern"]))) if p.is_file()]
        if not matches:
            return ToolResult.ok_text("(no matches)")
        shown = matches[:_MAX_MATCHES]
        suffix = "" if len(matches) <= _MAX_MATCHES else f"\n…[{len(matches) - _MAX_MATCHES} more]"
        return ToolResult.ok_text("\n".join(shown) + suffix)


class GrepTool:
    spec = ToolSpec(
        name="grep",
        description="Search workspace files for a regular expression; returns file:line matches.",
        parameters={
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Python regular expression."},
                "glob": {"type": "string", "description": "Optional file glob to limit search."},
            },
            "required": ["pattern"],
        },
        risk=RiskLevel.READ,
    )

    async def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        try:
            regex = re.compile(str(args["pattern"]))
        except re.error as exc:
            return ToolResult.error(f"invalid regex: {exc}")
        root = ctx.workspace_root.resolve()
        glob = str(args.get("glob") or "**/*")
        results: list[str] = []
        for path in sorted(root.glob(glob)):
            if not path.is_file() or _looks_binary(path):
                continue
            try:
                for i, line in enumerate(path.read_text("utf-8", errors="replace").splitlines(), 1):
                    if regex.search(line):
                        results.append(f"{to_rel(root, path)}:{i}: {line.strip()[:200]}")
                        if len(results) >= _MAX_MATCHES:
                            results.append("…[truncated]")
                            return ToolResult.ok_text("\n".join(results))
            except OSError:
                continue
        return ToolResult.ok_text("\n".join(results) or "(no matches)")


def _looks_binary(path: Path) -> bool:
    if path.suffix.lower() in {
        ".gguf",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".zip",
        ".exe",
        ".dll",
        ".pdf",
        ".pyc",
        ".so",
        ".bin",
        ".sqlite",
    }:
        return True
    try:
        return b"\x00" in path.read_bytes()[:1024]
    except OSError:
        return True


def read_tools() -> list[Any]:
    """All read-only filesystem tools."""
    return [ReadFileTool(), ListDirTool(), GlobTool(), GrepTool()]
