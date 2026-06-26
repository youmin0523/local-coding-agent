"""`list_symbols` — a fast structural outline of a file (functions, classes).

Boosts the agent's analysis ability: instead of reading a whole file to learn its
shape, it can pull an outline with line numbers. Python uses the stdlib ``ast``
(accurate, offline); other languages fall back to a lightweight regex. `READ`.
"""

from __future__ import annotations

import ast
import re
from typing import Any

from lca.tools.base import RiskLevel, ToolContext, ToolResult, ToolSpec
from lca.tools.util import safe_resolve, to_rel

# Generic definition patterns for non-Python files.
_DEF_RE = re.compile(
    r"^\s*(?:export\s+)?(?:async\s+)?(?:def|class|func|function|fn|interface|type|struct)\s+"
    r"([A-Za-z_][A-Za-z0-9_]*)",
)


class ListSymbolsTool:
    spec = ToolSpec(
        name="list_symbols",
        description=(
            "Return a structural outline of a file — its top-level and nested classes "
            "and functions with line numbers — without reading the whole file."
        ),
        parameters={
            "type": "object",
            "properties": {"path": {"type": "string", "description": "File path."}},
            "required": ["path"],
        },
        risk=RiskLevel.READ,
    )

    async def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        path = safe_resolve(ctx.workspace_root, str(args["path"]))
        if not path.is_file():
            return ToolResult.error(f"not a file: {args['path']}")
        text = path.read_text("utf-8", errors="replace")
        rel = to_rel(ctx.workspace_root, path)
        lines = _python_outline(text) if path.suffix == ".py" else _regex_outline(text)
        if not lines:
            return ToolResult.ok_text(f"{rel}: (no symbols found)")
        return ToolResult.ok_text(f"{rel}\n" + "\n".join(lines))


def _python_outline(source: str) -> list[str]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return _regex_outline(source)
    out: list[str] = []

    def visit(node: ast.AST, depth: int) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                out.append(f"  L{child.lineno}: {'  ' * depth}class {child.name}")
                visit(child, depth + 1)
            elif isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef):
                args = ", ".join(a.arg for a in child.args.args)
                out.append(f"  L{child.lineno}: {'  ' * depth}def {child.name}({args})")
                visit(child, depth + 1)

    visit(tree, 0)
    return out


def _regex_outline(source: str) -> list[str]:
    out: list[str] = []
    for i, line in enumerate(source.splitlines(), 1):
        match = _DEF_RE.match(line)
        if match:
            out.append(f"  L{i}: {match.group(0).strip()}")
    return out


_MAP_SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
    "dist",
    "build",
    ".lca",
    "data",
    "models",
}
_MAP_SUFFIXES = {".py", ".js", ".jsx", ".ts", ".tsx", ".go", ".rs", ".java", ".rb", ".php", ".cs"}
_MAP_MAX_FILES = 200


def top_level_symbols(source: str, *, python: bool) -> list[str]:
    """Top-level classes/functions of a file (compact, for the repo map)."""
    if python:
        try:
            tree = ast.parse(source)
        except SyntaxError:
            pass
        else:
            out: list[str] = []
            for node in tree.body:
                if isinstance(node, ast.ClassDef):
                    out.append(f"class {node.name}")
                elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                    out.append(f"def {node.name}")
            return out
    syms: list[str] = []
    for line in source.splitlines():
        if line and not line[0].isspace():  # top-level only (column 0)
            match = _DEF_RE.match(line)
            if match:
                syms.append(match.group(0).strip())
    return syms


class RepoMapTool:
    spec = ToolSpec(
        name="repo_map",
        description=(
            "A compact map of the repository: each code file with its top-level classes "
            "and functions. A fast whole-repo overview to orient before reading files."
        ),
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Subdirectory to map; default whole repo.",
                },
                "max_files": {"type": "integer", "description": "Cap on files listed."},
            },
        },
        risk=RiskLevel.READ,
    )

    async def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        root = ctx.workspace_root.resolve()
        scan = root / str(args["path"]) if args.get("path") else root
        limit = int(args.get("max_files") or _MAP_MAX_FILES)
        lines: list[str] = []
        for p in sorted(scan.rglob("*")):
            if len(lines) >= limit:
                lines.append("…[truncated — narrow with path]")
                break
            if not p.is_file() or any(d in _MAP_SKIP_DIRS for d in p.parts):
                continue
            if p.suffix.lower() not in _MAP_SUFFIXES:
                continue
            try:
                syms = top_level_symbols(
                    p.read_text("utf-8", errors="replace"), python=p.suffix == ".py"
                )
            except OSError:
                continue
            if syms:
                lines.append(f"{to_rel(root, p)}: {', '.join(syms)}")
        return ToolResult.ok_text("\n".join(lines) if lines else "(no symbols found)")
