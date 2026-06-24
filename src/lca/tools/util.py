"""Shared helpers for tools — chiefly workspace path confinement."""

from __future__ import annotations

from pathlib import Path

from lca.core.errors import ToolError


def safe_resolve(root: Path, path: str) -> Path:
    """Resolve ``path`` and guarantee it stays inside the workspace ``root``.

    Accepts paths relative to the workspace or absolute paths, but rejects
    anything that escapes the workspace (``..`` traversal, symlink breakout),
    so the model can never read or write outside the directory the user opened.
    """
    root_resolved = root.resolve()
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = root_resolved / candidate
    resolved = candidate.resolve()
    if resolved != root_resolved and root_resolved not in resolved.parents:
        raise ToolError(f"path {path!r} escapes the workspace root")
    return resolved


def to_rel(root: Path, path: Path) -> str:
    """Best-effort path relative to the workspace, for display."""
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)
