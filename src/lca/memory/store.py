"""SQLite-backed experience store (episodic / strategy / preference).

Reuses the same dependency-light approach as the RAG store (JSON vectors +
pure-Python cosine) so the whole memory subsystem is offline-capable and shares
the project's single embedding model. A separate DB from the code index keeps the
two concerns independent.
"""

from __future__ import annotations

import json
import math
import sqlite3
import time
from pathlib import Path

from lca.memory.models import MemoryItem


class MemoryStore:
    def __init__(self, db_path: Path | str = ":memory:") -> None:
        self._con = sqlite3.connect(str(db_path))
        self._con.row_factory = sqlite3.Row
        self._con.execute(
            """
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kind TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT '',
                vec TEXT NOT NULL,
                created_at REAL NOT NULL,
                UNIQUE(kind, title)
            )
            """
        )
        self._con.commit()

    def add(self, item: MemoryItem, vector: list[float], *, now: float | None = None) -> None:
        self._con.execute(
            "INSERT INTO memories(kind, title, content, source, vec, created_at) "
            "VALUES (?,?,?,?,?,?) "
            "ON CONFLICT(kind, title) DO UPDATE SET content=excluded.content, "
            "vec=excluded.vec, source=excluded.source, created_at=excluded.created_at",
            (
                item.kind,
                item.title,
                item.content,
                item.source,
                json.dumps(vector),
                now if now is not None else time.time(),
            ),
        )
        self._con.commit()

    def search(
        self, vector: list[float], k: int, *, kinds: tuple[str, ...] | None = None
    ) -> list[MemoryItem]:
        qnorm = math.sqrt(sum(x * x for x in vector)) or 1.0
        scored: list[tuple[float, sqlite3.Row]] = []
        query = "SELECT * FROM memories"
        params: tuple[object, ...] = ()
        if kinds:
            placeholders = ",".join("?" for _ in kinds)
            query += f" WHERE kind IN ({placeholders})"
            params = kinds
        for row in self._con.execute(query, params):
            vec = json.loads(row["vec"])
            dot = sum(a * b for a, b in zip(vector, vec, strict=False))
            vnorm = math.sqrt(sum(x * x for x in vec)) or 1.0
            scored.append((dot / (qnorm * vnorm), row))
        scored.sort(key=lambda t: t[0], reverse=True)
        return [
            MemoryItem(
                kind=row["kind"],
                title=row["title"],
                content=row["content"],
                source=row["source"],
                score=score,
            )
            for score, row in scored[:k]
        ]

    def count(self) -> int:
        return int(self._con.execute("SELECT COUNT(*) FROM memories").fetchone()[0])

    def dump(self, kind: str | None = None) -> list[MemoryItem]:
        """All stored items (optionally of one kind) — used to build training data."""
        query = "SELECT kind, title, content, source FROM memories"
        params: tuple[object, ...] = ()
        if kind:
            query += " WHERE kind = ?"
            params = (kind,)
        return [
            MemoryItem(
                kind=row["kind"], title=row["title"], content=row["content"], source=row["source"]
            )
            for row in self._con.execute(query, params)
        ]

    def close(self) -> None:
        self._con.close()
