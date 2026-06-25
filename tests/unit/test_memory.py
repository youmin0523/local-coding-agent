"""Experience memory: store search + the verified-only write gate."""

from __future__ import annotations

from lca.memory.memory import ExperienceMemory
from lca.memory.models import MemoryItem
from lca.memory.store import MemoryStore
from lca.rag.embedder import HashingEmbedder


def _mem() -> ExperienceMemory:
    return ExperienceMemory(MemoryStore(":memory:"), HashingEmbedder())


def test_store_add_and_search():
    store = MemoryStore(":memory:")
    emb = HashingEmbedder()
    items = [
        MemoryItem(kind="episodic", title="parse json safely", content="use json.loads in try"),
        MemoryItem(kind="episodic", title="render html page", content="use a template engine"),
    ]
    for it in items:
        store.add(it, emb.embed([f"{it.title} {it.content}"])[0])
    hits = store.search(emb.embed(["how to parse json"])[0], 1)
    assert hits and "json" in hits[0].title


async def test_remember_only_when_verified():
    mem = _mem()
    await mem.remember("do a thing", "the answer", verified=False)
    assert (await mem.recall("thing")) == []  # nothing written
    await mem.remember("do a thing", "the answer", verified=True)
    recalled = await mem.recall("thing")
    assert recalled and "the answer" in recalled[0]


async def test_note_caution_stores_a_lesson():
    mem = _mem()
    await mem.note_caution("solve the very hard widget problem", "judges disagreed")
    recalled = await mem.recall("hard widget problem")
    assert recalled
    assert "caution" in recalled[0].lower()


async def test_recall_is_bounded():
    mem = ExperienceMemory(MemoryStore(":memory:"), HashingEmbedder(), recall_k=2)
    for i in range(5):
        await mem.remember(f"task number {i} about widgets", f"answer {i}", verified=True)
    assert len(await mem.recall("widgets")) <= 2
