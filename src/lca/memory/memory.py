"""Experience memory — weight-free self-improvement.

The agent recalls a *small* number (k=1-2) of relevant past experiences into
context, and writes a new experience ONLY when a result was verified. That single
write-gate ("remember only what was verified") is the entire anti-poisoning
defense: an unverified or hallucinated "success" can never enter the store and
later mislead the agent.

`Memory` is the interface the agent depends on (decoupled from verification — it
takes a plain ``verified`` flag), so it is trivially faked in tests.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from lca.memory.models import MemoryItem
from lca.memory.store import MemoryStore
from lca.observability.logging import get_logger
from lca.rag.embedder import Embedder

log = get_logger("memory")


@runtime_checkable
class Memory(Protocol):
    async def recall(self, query: str, k: int = 2) -> list[str]: ...

    async def remember(self, task: str, answer: str, *, verified: bool) -> None: ...

    async def note_caution(self, task: str, reason: str) -> None: ...


class ExperienceMemory:
    def __init__(self, store: MemoryStore, embedder: Embedder, *, recall_k: int = 2) -> None:
        self._store = store
        self._embedder = embedder
        self._recall_k = recall_k

    async def recall(self, query: str, k: int = 2) -> list[str]:
        vec = self._embedder.embed([query])[0]
        items = self._store.search(vec, k or self._recall_k)
        return [item.render() for item in items]

    async def remember(self, task: str, answer: str, *, verified: bool) -> None:
        # THE write gate: nothing unverified is ever persisted.
        if not verified:
            return
        item = _distill(task, answer)
        if not item.content:
            return
        vector = self._embedder.embed([f"{item.title}\n{item.content}"])[0]
        self._store.add(item, vector)
        log.info("memory.remembered", title=item.title[:60])

    async def note_caution(self, task: str, reason: str) -> None:
        """Learn from a failure/abstention — store a *lesson* (not a fabricated solution).

        Safe under the anti-poisoning rule: a caution records "this was hard to verify,
        check first", never an unverified answer.
        """
        first = next((ln for ln in task.strip().splitlines() if ln.strip()), "task")
        item = MemoryItem(
            kind="strategy",
            title=f"caution: {first.strip()[:100]}",
            content=(
                f"A prior attempt at this could not be verified ({reason[:160]}). "
                "Gather evidence and run checks before asserting an answer."
            ),
            source="caution",
        )
        vector = self._embedder.embed([f"{item.title}\n{item.content}"])[0]
        self._store.add(item, vector)
        log.info("memory.caution", title=item.title[:60])


def _distill(task: str, answer: str) -> MemoryItem:
    """Heuristic distillation of a verified task→answer into an episodic memory.

    (An LLM-based distiller producing richer 'strategy' lessons can replace this
    later; the heuristic keeps memory fully offline and deterministic.)
    """
    first_line = next((ln for ln in task.strip().splitlines() if ln.strip()), "task")
    return MemoryItem(
        kind="episodic",
        title=first_line.strip()[:120],
        content=answer.strip()[:500],
        source="verified-success",
    )
