"""RAG over the user's codebase (chunking, embeddings, hybrid retrieval).

Only the retrieval interface lives here so far; the concrete store, chunker,
embedder, indexer, and hybrid retriever arrive in M3.
"""

from lca.rag.retriever import Retriever, ScoredChunk

__all__ = ["Retriever", "ScoredChunk"]
