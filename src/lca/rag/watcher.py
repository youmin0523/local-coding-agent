"""File-change watcher that keeps the index fresh.

Uses watchdog (optional ``rag`` extra) to debounce filesystem events and re-index
only the changed files. If watchdog isn't installed, `start()` is a no-op and the
user re-indexes manually with `lca index` — the agent still works, just without
live updates.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from lca.observability.logging import get_logger
from lca.rag.indexer import SKIP_DIRS, Indexer

log = get_logger("rag.watcher")


class IndexWatcher:
    def __init__(self, indexer: Indexer, root: Path) -> None:
        self._indexer = indexer
        self._root = root
        self._observer: Any = None

    def start(self) -> bool:
        """Start watching; return False if watchdog is unavailable."""
        try:
            from watchdog.events import FileSystemEventHandler
            from watchdog.observers import Observer
        except Exception:
            log.info("rag.watcher.unavailable", detail="watchdog not installed; manual reindex")
            return False

        indexer = self._indexer

        class _Handler(FileSystemEventHandler):
            def on_any_event(self, event: object) -> None:
                src = getattr(event, "src_path", None)
                is_dir = getattr(event, "is_directory", False)
                if not src or is_dir:
                    return
                path = Path(src)
                if any(part in SKIP_DIRS for part in path.parts):
                    return
                try:
                    indexer.index_file(path)
                except Exception as exc:  # never let a watcher callback crash
                    log.warning("rag.watcher.index_failed", path=str(path), error=str(exc))

        self._observer = Observer()
        self._observer.schedule(_Handler(), str(self._root), recursive=True)
        self._observer.start()
        log.info("rag.watcher.started", root=str(self._root))
        return True

    def stop(self) -> None:
        if self._observer is not None:
            self._observer.stop()
            self._observer.join(timeout=5)
            self._observer = None
