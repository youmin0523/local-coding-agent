"""Filesystem locations for lca's local data.

Everything lca persists (SQLite DBs for RAG + memory, logs, the model registry,
LoRA adapters) lives under a single per-user application directory so the tool
leaves no trace in the user's project unless explicitly told to.

On Windows this resolves to ``%LOCALAPPDATA%\\lca``; elsewhere it follows the
XDG-ish ``~/.local/share/lca`` convention. The implementation is intentionally
dependency-free (no platformdirs) to keep the base install minimal.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def data_dir() -> Path:
    """Return the root directory for lca's persistent data, creating it lazily."""
    env_override = os.environ.get("LCA_DATA_DIR")
    if env_override:
        root = Path(env_override)
    elif os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local")
        root = Path(base) / "lca"
    else:
        base = os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share")
        root = Path(base) / "lca"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _subdir(name: str) -> Path:
    path = data_dir() / name
    path.mkdir(parents=True, exist_ok=True)
    return path


def logs_dir() -> Path:
    """Directory for rotated structured logs."""
    return _subdir("logs")


def index_db_path() -> Path:
    """SQLite file backing the code RAG index (sqlite-vec + FTS5)."""
    return _subdir("index") / "code_index.sqlite"


def memory_db_path() -> Path:
    """SQLite file backing the experience memory (episodic/strategy/preference)."""
    return _subdir("memory") / "experience.sqlite"


def models_dir() -> Path:
    """Where downloaded GGUF models / LoRA adapters are tracked."""
    return _subdir("models")
