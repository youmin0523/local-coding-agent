"""Swappable LLM engine adapters behind one `LLMProvider` interface."""

from lca.providers.base import (
    ChatChunk,
    ChatRequest,
    LLMProvider,
    ProviderCaps,
    ProviderHealth,
    ToolSchema,
)
from lca.providers.fake import FakeProvider
from lca.providers.llamacpp import LlamaCppProvider
from lca.providers.openai_compat import OpenAICompatProvider
from lca.providers.registry import build_provider, resolve_model

__all__ = [
    "ChatChunk",
    "ChatRequest",
    "FakeProvider",
    "LLMProvider",
    "LlamaCppProvider",
    "OpenAICompatProvider",
    "ProviderCaps",
    "ProviderHealth",
    "ToolSchema",
    "build_provider",
    "resolve_model",
]
