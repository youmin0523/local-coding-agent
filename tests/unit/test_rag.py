"""RAG: chunking, store search, hybrid fusion, incremental indexing, search tool."""

from __future__ import annotations

from pathlib import Path

from lca.core.session import Session
from lca.permissions.approver import AutoApprover
from lca.rag.chunker import chunk_source
from lca.rag.embedder import HashingEmbedder
from lca.rag.hybrid import HybridRetriever
from lca.rag.indexer import Indexer
from lca.rag.store import SqliteVectorStore
from lca.tools.base import ToolContext
from lca.tools.search_code import SearchCodeTool

TAX = "def calculate_tax(income):\n    return income * 0.2  # tax rate on income"
HTML = "def render_html(template):\n    return f'<html>{template}</html>'  # render page"


def _store_with_two_chunks() -> SqliteVectorStore:
    store = SqliteVectorStore(":memory:")
    emb = HashingEmbedder()
    chunks = chunk_source("tax.py", TAX) + chunk_source("web.py", HTML)
    store.upsert(chunks, emb.embed([c.text for c in chunks]))
    return store


def test_chunk_source_covers_all_lines():
    text = "\n".join(f"line {i}" for i in range(1, 201))
    chunks = chunk_source("big.txt", text, target_lines=50)
    assert len(chunks) >= 3
    assert chunks[0].start_line == 1
    assert chunks[-1].end_line == 200


def test_dense_and_bm25_find_relevant_chunk():
    store = _store_with_two_chunks()
    emb = HashingEmbedder()
    dense = store.search_dense(emb.embed(["income tax calculation"])[0], 2)
    assert dense and dense[0].path == "tax.py"
    bm25 = store.search_bm25("income tax", 2)
    assert bm25 and bm25[0].path == "tax.py"


async def test_hybrid_retriever_ranks_relevant_first():
    store = _store_with_two_chunks()
    retriever = HybridRetriever(store, HashingEmbedder(), k=1)
    results = await retriever.retrieve("how is income tax calculated?")
    assert len(results) == 1
    assert results[0].path == "tax.py"


def test_indexer_is_incremental(tmp_path: Path):
    (tmp_path / "m.py").write_text("def a():\n    return 1\n", encoding="utf-8")
    store = SqliteVectorStore(":memory:")
    idx = Indexer(store, HashingEmbedder(), root=tmp_path)

    s1 = idx.index_all()
    assert s1.files_indexed == 1 and s1.chunks >= 1 and store.count() >= 1

    s2 = idx.index_all()
    assert s2.files_indexed == 0 and s2.files_skipped == 1  # unchanged → skipped

    (tmp_path / "m.py").unlink()
    s3 = idx.index_all()
    assert s3.files_removed == 1 and store.count() == 0


async def test_search_code_tool_returns_citations(tmp_path: Path):
    store = _store_with_two_chunks()
    tool = SearchCodeTool(HybridRetriever(store, HashingEmbedder()))
    ctx = ToolContext(
        workspace_root=tmp_path, approver=AutoApprover(), session=Session(workspace_root=tmp_path)
    )
    res = await tool.run({"query": "income tax"}, ctx)
    assert res.ok
    assert "tax.py" in res.content
    assert any(a.kind == "citation" for a in res.artifacts)
