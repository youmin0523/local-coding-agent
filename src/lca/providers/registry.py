"""Provider factory + logical-model resolution.

The engine is chosen once (llama.cpp by default; Ollama as a no-grammar
fallback) and exposed as a single `LLMProvider`. The *model* is selected
per-request: the agent asks for the logical ``"brain"`` or ``"fast"`` model and
this module maps those to the concrete model ids configured in settings.
"""

from __future__ import annotations

from typing import Literal

import httpx

from lca.config.settings import Settings, get_settings
from lca.providers.base import LLMProvider
from lca.providers.llamacpp import LlamaCppProvider
from lca.providers.openai_compat import OpenAICompatProvider
from lca.providers.retry import RetryingProvider

EngineKind = Literal["llamacpp", "ollama", "openai-compat"]
LogicalModel = Literal["brain", "fast"]

# Common local engine endpoints, in preference order: LM Studio, llama-server, Ollama.
_CANDIDATE_URLS = (
    "http://127.0.0.1:1234/v1",
    "http://127.0.0.1:8080/v1",
    "http://127.0.0.1:11434/v1",
)


def detect_base_url(configured: str, *, key: str = "", timeout: float = 1.0) -> str | None:
    """Return a reachable engine URL, or ``None`` if none answered.

    Tries the configured URL first (respecting an explicit setting), then the common
    local ports. A candidate counts only if it returns < 400 **and** the body looks like
    an OpenAI ``/models`` response (a JSON ``data`` list) — so a stray service squatting
    on the port (returning 200/401/404) isn't mistaken for the engine. Quick, never raises.
    """
    seen: set[str] = set()
    headers = {"Authorization": f"Bearer {key}"} if key else None
    for url in (configured, *_CANDIDATE_URLS):
        norm = url.rstrip("/")
        if norm in seen:
            continue
        seen.add(norm)
        try:
            resp = httpx.get(f"{norm}/models", headers=headers, timeout=timeout)
            if resp.status_code < 400 and isinstance(resp.json().get("data"), list):
                return url
        except Exception:
            continue
    return None


_DEFAULT_BASE_URL = "http://127.0.0.1:8080/v1"  # mirrors LLMSettings.base_url default
_resolved_url: str | None = None


def build_provider(
    settings: Settings | None = None, *, engine: EngineKind = "llamacpp", retries: int = 3
) -> LLMProvider:
    settings = settings or get_settings()
    url = settings.llm.base_url
    key = settings.llm.api_key
    # If the user didn't override the endpoint, auto-detect a reachable local engine
    # once per process (LM Studio :1234 / llama-server :8080 / Ollama :11434).
    if url == _DEFAULT_BASE_URL:
        global _resolved_url
        # Only memoize a *positive* detection — if nothing answered (engine not up yet),
        # leave the cache empty so a later call re-detects once the engine starts.
        if _resolved_url is None:
            _resolved_url = detect_base_url(url, key=key)
        url = _resolved_url or _DEFAULT_BASE_URL
    timeout = settings.llm.request_timeout_s
    inner: LLMProvider = (
        LlamaCppProvider(url, key, timeout)
        if engine == "llamacpp"
        # Ollama and other OpenAI-compatible servers: same wire format, no grammar.
        else OpenAICompatProvider(url, key, timeout)
    )
    return RetryingProvider(inner, attempts=retries) if retries > 1 else inner


def resolve_model(logical: LogicalModel, settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    return settings.llm.brain_model if logical == "brain" else settings.llm.fast_model
