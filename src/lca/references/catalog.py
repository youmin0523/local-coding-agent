"""Local reference catalog of official docs + how-to for languages/frameworks.

So the agent can apply *any* technology, it first consults this curated, offline,
cited catalog (official docs URL + quickstart + idioms); for anything not present
it falls back to the live search → fetch → cite chain. The catalog lives in
``catalog.jsonl`` next to this module and ships with the package.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, ValidationError

_CATALOG = Path(__file__).parent / "catalog.jsonl"


class ReferenceEntry(BaseModel):
    tech: str
    category: str = ""
    official_docs: str = ""
    install: str = ""
    quickstart: str = ""
    idioms: list[str] = []
    when_to_use: str = ""

    def render(self) -> str:
        out = [f"# {self.tech} ({self.category})".rstrip(" ()")]
        if self.official_docs:
            out.append(f"Official docs: {self.official_docs}")
        if self.when_to_use:
            out.append(f"When to use: {self.when_to_use}")
        if self.install:
            out.append(f"Install: {self.install}")
        if self.quickstart:
            out.append(f"Quickstart: {self.quickstart}")
        if self.idioms:
            out.append("Idioms:\n" + "\n".join(f"- {i}" for i in self.idioms))
        return "\n".join(out)


@lru_cache(maxsize=1)
def load_catalog() -> tuple[ReferenceEntry, ...]:
    if not _CATALOG.exists():
        return ()
    entries: list[ReferenceEntry] = []
    for line in _CATALOG.read_text("utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(ReferenceEntry.model_validate_json(line))
        except ValidationError:
            continue
    return tuple(entries)


def search_catalog(query: str, limit: int = 3) -> list[ReferenceEntry]:
    """Rank catalog entries against a tech/keyword query (offline, deterministic)."""
    q = query.lower().strip()
    if not q:
        return []
    words = q.split()
    scored: list[tuple[int, ReferenceEntry]] = []
    for entry in load_catalog():
        tech = entry.tech.lower()
        hay = f"{tech} {entry.category} {' '.join(entry.idioms)} {entry.when_to_use}".lower()
        score = 0
        if q in tech:
            score += 5
        score += sum(2 for w in words if w in tech)
        score += sum(1 for w in words if w in hay)
        if score:
            scored.append((score, entry))
    scored.sort(key=lambda t: t[0], reverse=True)
    return [e for _, e in scored[:limit]]


def all_techs() -> list[str]:
    return [e.tech for e in load_catalog()]
