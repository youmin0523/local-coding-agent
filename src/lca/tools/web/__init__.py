"""Web tools: search (free backend chain) and fetch (with citation)."""

from lca.tools.web.fetch import FetchUrlTool, extract_text
from lca.tools.web.search import SearchResult, WebSearchTool, build_backends

__all__ = ["FetchUrlTool", "SearchResult", "WebSearchTool", "build_backends", "extract_text"]
