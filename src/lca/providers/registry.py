"""Provider factory + logical-model resolution.

The engine is chosen once (llama.cpp by default; Ollama as a no-grammar
fallback) and exposed as a single `LLMProvider`. The *model* is selected
per-request: the agent asks for the logical ``"brain"`` or ``"fast"`` model and
this module maps those to the concrete model ids configured in settings.
"""

from __future__ import annotations

from typing import Literal

from lca.config.settings import Settings, get_settings
from lca.providers.base import LLMProvider
from lca.providers.llamacpp import LlamaCppProvider
from lca.providers.openai_compat import OpenAICompatProvider

EngineKind = Literal["llamacpp", "ollama", "openai-compat"]
LogicalModel = Literal["brain", "fast"]


def build_provider(
    settings: Settings | None = None, *, engine: EngineKind = "llamacpp"
) -> LLMProvider:
    settings = settings or get_settings()
    url = settings.llm.base_url
    key = settings.llm.api_key
    timeout = settings.llm.request_timeout_s
    if engine == "llamacpp":
        return LlamaCppProvider(url, key, timeout)
    # Ollama and other OpenAI-compatible servers: same wire format, no grammar.
    return OpenAICompatProvider(url, key, timeout)


def resolve_model(logical: LogicalModel, settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    return settings.llm.brain_model if logical == "brain" else settings.llm.fast_model
