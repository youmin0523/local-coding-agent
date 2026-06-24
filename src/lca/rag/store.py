"""Vector + keyword store for code chunks.

Backed by stdlib ``sqlite3``: dense vectors are stored as JSON and scored with
pure-Python cosine (fast enough at single-repo scale), and keyword search uses
SQLite's FTS5 when available (with a LIKE-based fallback otherwise). This keeps
the whole RAG stack dependency-free and offline-capable; the `VectorStore`
Protocol lets us swap in sqlite-vec / ANN later without touching callers.
"""

from __future__ import annotations

import json
import math
import re
import sqlite3
from pathlib import Path
from typing import Protocol

from lca.observability.logging import get_logger
from lca.rag.chunker import Chunk
from lca.rag.retriever import ScoredChunk

log = get_logger("rag.store")
_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")


class VectorStore(Protocol):
    def upsert(self, chunks: list[Chunk], vectors: list[list[float]]) -> None: ...
    def search_dense(self, vector: list[float], k: int) -> list[ScoredChunk]: ...
    def search_bm25(self, query: str, k: int) -> list[ScoredChunk]: ...
    def delete_by_path(self, path: str) -> None: ...


class SqliteVectorStore:
    def __init__(self, db_path: Path | str = ":memory:") -> None:
        self._db = str(db_path)
        self._con = sqlite3.connect(self._db)
        self._con.row_factory = sqlite3.Row
        self._fts = self._probe_fts5()
        self._init_schema()

    # -- schema ---------------------------------------------------------------
    def _probe_fts5(self) -> bool:
        try:
            self._con.execute("CREATE VIRTUAL TABLE temp.__fts_probe USING fts5(x)")
            self._con.execute("DROP TABLE temp.__fts_probe")
            return True
        except sqlite3.OperationalError:
            log.warning("rag.store.no_fts5", detail="FTS5 unavailable; using LIKE fallback")
            return False

    def _init_schema(self) -> None:
        self._con.executescript(
            """
            CREATE TABLE IF NOT EXISTS chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT NOT NULL,
                start_line INTEGER NOT NULL,
                end_line INTEGER NOT NULL,
                text TEXT NOT NULL,
                vec TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_chunks_path ON chunks(path);
            CREATE TABLE IF NOT EXISTS files (
                path TEXT PRIMARY KEY,
                mtime REAL NOT NULL,
                size INTEGER NOT NULL
            );
            """
        )
        if self._fts:
            # A standard (not contentless) FTS5 table so rows can be DELETEd by rowid
            # during incremental re-indexing.
            self._con.execute("CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(text)")
        self._con.commit()

    # -- writes ---------------------------------------------------------------
    def upsert(self, chunks: list[Chunk], vectors: list[list[float]]) -> None:
        if len(chunks) != len(vectors):
            raise ValueError("chunks and vectors length mismatch")
        cur = self._con.cursor()
        for chunk, vec in zip(chunks, vectors, strict=True):
            cur.execute(
                "INSERT INTO chunks(path, start_line, end_line, text, vec) VALUES (?,?,?,?,?)",
                (chunk.path, chunk.start_line, chunk.end_line, chunk.text, json.dumps(vec)),
            )
            if self._fts:
                cur.execute(
                    "INSERT INTO chunks_fts(rowid, text) VALUES (?, ?)",
                    (cur.lastrowid, chunk.text),
                )
        self._con.commit()

    def delete_by_path(self, path: str) -> None:
        cur = self._con.cursor()
        if self._fts:
            ids = [r[0] for r in cur.execute("SELECT id FROM chunks WHERE path=?", (path,))]
            cur.executemany("DELETE FROM chunks_fts WHERE rowid=?", [(i,) for i in ids])
        cur.execute("DELETE FROM chunks WHERE path=?", (path,))
        self._con.commit()

    # -- file metadata (for incremental indexing) -----------------------------
    def get_file_meta(self, path: str) -> tuple[float, int] | None:
        row = self._con.execute("SELECT mtime, size FROM files WHERE path=?", (path,)).fetchone()
        return (row["mtime"], row["size"]) if row else None

    def set_file_meta(self, path: str, mtime: float, size: int) -> None:
        self._con.execute(
            "INSERT INTO files(path, mtime, size) VALUES (?,?,?) "
            "ON CONFLICT(path) DO UPDATE SET mtime=excluded.mtime, size=excluded.size",
            (path, mtime, size),
        )
        self._con.commit()

    def indexed_paths(self) -> set[str]:
        return {r[0] for r in self._con.execute("SELECT path FROM files")}

    def count(self) -> int:
        return int(self._con.execute("SELECT COUNT(*) FROM chunks").fetchone()[0])

    # -- search ---------------------------------------------------------------
    def search_dense(self, vector: list[float], k: int) -> list[ScoredChunk]:
        qnorm = math.sqrt(sum(x * x for x in vector)) or 1.0
        scored: list[tuple[float, sqlite3.Row]] = []
        for row in self._con.execute("SELECT * FROM chunks"):
            vec = json.loads(row["vec"])
            dot = sum(a * b for a, b in zip(vector, vec, strict=False))
            vnorm = math.sqrt(sum(x * x for x in vec)) or 1.0
            scored.append((dot / (qnorm * vnorm), row))
        scored.sort(key=lambda t: t[0], reverse=True)
        return [_to_scored(row, score) for score, row in scored[:k]]

    def search_bm25(self, query: str, k: int) -> list[ScoredChunk]:
        tokens = _TOKEN_RE.findall(query.lower())
        if not tokens:
            return []
        if self._fts:
            match = " OR ".join(f'"{t}"' for t in tokens)
            rows = self._con.execute(
                "SELECT c.*, bm25(chunks_fts) AS score FROM chunks_fts "
                "JOIN chunks c ON c.id = chunks_fts.rowid "
                "WHERE chunks_fts MATCH ? ORDER BY score LIMIT ?",
                (match, k),
            ).fetchall()
            return [_to_scored(r, -float(r["score"])) for r in rows]
        return self._like_search(tokens, k)

    def _like_search(self, tokens: list[str], k: int) -> list[ScoredChunk]:
        scored: list[tuple[float, sqlite3.Row]] = []
        for row in self._con.execute("SELECT * FROM chunks"):
            lowered = row["text"].lower()
            hits = sum(lowered.count(t) for t in tokens)
            if hits:
                scored.append((float(hits), row))
        scored.sort(key=lambda t: t[0], reverse=True)
        return [_to_scored(row, score) for score, row in scored[:k]]

    def close(self) -> None:
        self._con.close()


def _to_scored(row: sqlite3.Row, score: float) -> ScoredChunk:
    return ScoredChunk(
        path=row["path"],
        start_line=row["start_line"],
        end_line=row["end_line"],
        text=row["text"],
        score=score,
    )
