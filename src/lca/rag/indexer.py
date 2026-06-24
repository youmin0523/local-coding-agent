"""Repository indexer.

Walks the workspace, chunks code/text files, embeds them, and upserts into the
store. Indexing is incremental: a file is re-chunked only when its mtime/size
changed, and files deleted from disk are pruned from the index. This keeps
re-indexing on every edit cheap (the file watcher in `watcher.py` drives it).
"""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel

from lca.observability.logging import get_logger
from lca.rag.chunker import chunk_source
from lca.rag.embedder import Embedder
from lca.rag.store import SqliteVectorStore

log = get_logger("rag.indexer")

SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
    "dist",
    "build",
    "data",
    "models",
    ".idea",
    ".vscode",
}
DEFAULT_SUFFIXES = {
    ".py",
    ".pyi",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".go",
    ".rs",
    ".java",
    ".c",
    ".h",
    ".cpp",
    ".hpp",
    ".rb",
    ".cs",
    ".php",
    ".sh",
    ".ps1",
    ".sql",
    ".html",
    ".css",
    ".scss",
    ".md",
    ".rst",
    ".toml",
    ".yaml",
    ".yml",
    ".json",
    ".txt",
}
_MAX_FILE_BYTES = 1_000_000


class IndexStats(BaseModel):
    files_indexed: int = 0
    files_skipped: int = 0
    files_removed: int = 0
    chunks: int = 0


class Indexer:
    def __init__(
        self,
        store: SqliteVectorStore,
        embedder: Embedder,
        *,
        root: Path,
        suffixes: set[str] | None = None,
    ) -> None:
        self._store = store
        self._embedder = embedder
        self._root = root.resolve()
        self._suffixes = suffixes or DEFAULT_SUFFIXES

    def index_all(self) -> IndexStats:
        stats = IndexStats()
        seen: set[str] = set()
        for file in self._walk():
            rel = file.relative_to(self._root).as_posix()
            seen.add(rel)
            if self._index_if_changed(file, rel):
                stats.files_indexed += 1
                stats.chunks += self._chunk_count(rel)
            else:
                stats.files_skipped += 1
        # prune files removed from disk
        for gone in self._store.indexed_paths() - seen:
            self._store.delete_by_path(gone)
            stats.files_removed += 1
        log.info("rag.index.done", **stats.model_dump())
        return stats

    def index_file(self, file: Path) -> None:
        if not file.is_file():
            rel = self._safe_rel(file)
            if rel:
                self._store.delete_by_path(rel)
            return
        rel = self._safe_rel(file)
        if rel:
            self._index_if_changed(file, rel, force=True)

    def _index_if_changed(self, file: Path, rel: str, *, force: bool = False) -> bool:
        try:
            stat = file.stat()
        except OSError:
            return False
        meta = self._store.get_file_meta(rel)
        if not force and meta is not None and meta == (stat.st_mtime, stat.st_size):
            return False
        try:
            text = file.read_text("utf-8")
        except (OSError, UnicodeDecodeError):
            return False
        self._store.delete_by_path(rel)
        chunks = chunk_source(rel, text)
        if chunks:
            vectors = self._embedder.embed([c.text for c in chunks])
            self._store.upsert(chunks, vectors)
        self._store.set_file_meta(rel, stat.st_mtime, stat.st_size)
        return True

    def _chunk_count(self, rel: str) -> int:
        return len(chunk_source(rel, (self._root / rel).read_text("utf-8", errors="replace")))

    def _walk(self) -> list[Path]:
        out: list[Path] = []
        for dirpath, dirnames, filenames in os.walk(self._root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
            for name in filenames:
                path = Path(dirpath) / name
                if path.suffix.lower() in self._suffixes and path.stat().st_size <= _MAX_FILE_BYTES:
                    out.append(path)
        return out

    def _safe_rel(self, file: Path) -> str | None:
        try:
            return file.resolve().relative_to(self._root).as_posix()
        except ValueError:
            return None
