"""Export verified experiences from lca's memory into an SFT dataset.

This closes the self-improvement loop: the experience memory only ever stores
EXECUTION-VERIFIED task→answer pairs (see lca.memory), so it is exactly the
rejection-sampling (RFT/STaR) corpus we want to fine-tune the 7B on — no separate
data pipeline needed.

Pure-Python (stdlib sqlite3); run anywhere. Output: data/sft.jsonl
(one {"prompt", "response"} per line).

Usage:
    python training/export_dataset.py            # reads the default memory DB
    python training/export_dataset.py --db PATH --out data/sft.jsonl
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
from pathlib import Path


def default_db() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / ".local" / "share")
    return Path(base) / "lca" / "memory" / "experience.sqlite"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=default_db())
    parser.add_argument("--out", type=Path, default=Path("data/sft.jsonl"))
    parser.add_argument("--source", default="verified-success")
    args = parser.parse_args()

    if not args.db.exists():
        raise SystemExit(f"memory DB not found: {args.db} (use the agent first to accumulate it)")

    con = sqlite3.connect(str(args.db))
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT title, content FROM memories WHERE source = ? AND kind = 'episodic'",
        (args.source,),
    ).fetchall()
    con.close()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps({"prompt": row["title"], "response": row["content"]}) + "\n")
    print(f"wrote {len(rows)} verified examples to {args.out}")


if __name__ == "__main__":
    main()
