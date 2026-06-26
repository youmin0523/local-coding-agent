"""File checkpointing so the agent's edits are reversible.

Before any write/edit, the prior state of the file (its content, or "did not
exist") is appended to a journal under ``<workspace>/.lca/checkpoints/``. ``lca
undo`` pops the last entry and restores it — repeat to walk back. This is the
safety net every other coding agent has (Cursor/Cline/aider-via-git) and lca did
not.
"""

from __future__ import annotations

import json
from pathlib import Path

from lca.tools.util import to_rel

_MAX_SNAPSHOT_BYTES = 2_000_000  # don't journal huge/binary files


class Checkpointer:
    def __init__(self, workspace_root: Path) -> None:
        self._root = workspace_root.resolve()
        self._dir = self._root / ".lca" / "checkpoints"
        self._journal = self._dir / "journal.jsonl"

    def record(self, path: Path) -> None:
        """Snapshot a file's current state before it is created or overwritten."""
        existed = path.is_file()
        content: str | None = None
        if existed:
            try:
                if path.stat().st_size > _MAX_SNAPSHOT_BYTES:
                    return  # too big to journal; skip (rare for source files)
                content = path.read_text("utf-8", errors="replace")
            except OSError:
                return
        entry = {"rel": to_rel(self._root, path), "existed": existed, "content": content}
        self._dir.mkdir(parents=True, exist_ok=True)
        with self._journal.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def undo_last(self) -> str | None:
        """Restore the most recently snapshotted file. Returns a description or None."""
        if not self._journal.is_file():
            return None
        lines = [ln for ln in self._journal.read_text("utf-8").splitlines() if ln.strip()]
        if not lines:
            return None
        entry = json.loads(lines[-1])
        remaining = lines[:-1]
        self._journal.write_text(
            "\n".join(remaining) + ("\n" if remaining else ""), encoding="utf-8"
        )
        target = self._root / entry["rel"]
        if entry["existed"]:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(entry["content"] or "", encoding="utf-8")
            return f"restored {entry['rel']}"
        if target.is_file():
            target.unlink()
        return f"removed {entry['rel']} (it was newly created)"

    def pending(self) -> int:
        """How many undo steps are available."""
        if not self._journal.is_file():
            return 0
        return sum(1 for ln in self._journal.read_text("utf-8").splitlines() if ln.strip())
