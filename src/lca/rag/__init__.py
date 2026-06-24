"""RAG over the user's codebase: chunking, CPU embeddings, hybrid retrieval.

The agent depends only on `Retriever`/`ScoredChunk`; the rest (store, chunker,
embedder, indexer, watcher) are the concrete, dependency-light implementation.
"""

from lca.rag.chunker import Chunk, chunk_source
from lca.rag.embedder import Embedder, FastEmbedEmbedder, HashingEmbedder, default_embedder
from lca.rag.hybrid import HybridRetriever
from lca.rag.indexer import Indexer, IndexStats
from lca.rag.retriever import Retriever, ScoredChunk
from lca.rag.store import SqliteVectorStore, VectorStore
from lca.rag.watcher import IndexWatcher

__all__ = [
    "Chunk",
    "Embedder",
    "FastEmbedEmbedder",
    "HashingEmbedder",
    "HybridRetriever",
    "IndexStats",
    "IndexWatcher",
    "Indexer",
    "Retriever",
    "ScoredChunk",
    "SqliteVectorStore",
    "VectorStore",
    "chunk_source",
    "default_embedder",
]
