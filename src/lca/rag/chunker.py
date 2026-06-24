"""Code chunking.

Prefers AST-aware boundaries (via tree-sitter, optional ``rag`` extra) so chunks
fall on whole top-level definitions instead of mid-function; falls back to a
sliding line-window when tree-sitter or the language grammar is unavailable. Each
chunk records its line range so retrieved context is citeable as ``path:start-end``.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

_TARGET_LINES = 80
_OVERLAP = 10

# File suffix → tree-sitter language name (only used if tree-sitter is installed).
_LANG_BY_SUFFIX = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".hpp": "cpp",
    ".rb": "ruby",
}


class Chunk(BaseModel):
    path: str
    start_line: int
    end_line: int
    text: str


def chunk_source(path: str, text: str, *, target_lines: int = _TARGET_LINES) -> list[Chunk]:
    lines = text.splitlines()
    if not lines:
        return []
    spans = _ast_spans(path, text) or _window_spans(len(lines), target_lines)
    chunks: list[Chunk] = []
    for start, end in spans:
        body = "\n".join(lines[start - 1 : end])
        if body.strip():
            chunks.append(Chunk(path=path, start_line=start, end_line=end, text=body))
    return chunks


def _window_spans(n_lines: int, target: int) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    step = max(1, target - _OVERLAP)
    start = 1
    while start <= n_lines:
        end = min(n_lines, start + target - 1)
        spans.append((start, end))
        if end == n_lines:
            break
        start += step
    return spans


def _ast_spans(path: str, text: str) -> list[tuple[int, int]] | None:
    """Top-level definition spans, grouped to ~target size. None if unavailable."""
    lang = _LANG_BY_SUFFIX.get(Path(path).suffix.lower())
    if lang is None:
        return None
    try:
        from tree_sitter_language_pack import get_parser
    except Exception:
        return None
    try:
        parser = get_parser(lang)
        tree = parser.parse(text.encode("utf-8"))
    except Exception:
        return None

    children = tree.root_node.children
    if not children:
        return None

    raw = [(c.start_point[0] + 1, c.end_point[0] + 1) for c in children]
    # Merge adjacent small nodes so a chunk is roughly target-sized but never
    # splits a single definition.
    merged: list[list[int]] = []
    for start, end in raw:
        if merged and (end - merged[-1][0] + 1) <= _TARGET_LINES:
            merged[-1][1] = end
        else:
            merged.append([start, end])
    return [(s, e) for s, e in merged]
