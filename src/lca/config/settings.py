"""Typed application settings, loaded from environment / ``.env``.

Read with the ``LCA_`` prefix and ``__`` as the nesting delimiter, e.g.
``LCA_LLM__BASE_URL`` maps to ``settings.llm.base_url``.

This is the lowest layer of the package and must not import any domain module
(``permissions``, ``providers``, …) — those depend on it, not the reverse.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

AutonomyLiteral = Literal["gated", "autonomous", "plan"]


class LLMSettings(BaseModel):
    """Connection + model selection for the local inference engine."""

    base_url: str = "http://127.0.0.1:8080/v1"
    api_key: str = "not-needed-for-local"
    # Logical model names; must match the ids the engine serves (see `lca doctor`).
    brain_model: str = "qwen3-coder-30b-a3b-instruct"
    fast_model: str = "qwen2.5-coder-7b-instruct"
    # Hard cap, deliberately far below the model's nominal max (8GB VRAM tier).
    max_context_tokens: int = 16_384
    request_timeout_s: float = 600.0


class SearchSettings(BaseModel):
    """Web-search backends. The agent stays local; only the search tool reaches out."""

    tavily_api_key: str = ""
    searxng_url: str = ""
    max_results: int = 5


class LogSettings(BaseModel):
    format: Literal["console", "json"] = "console"
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="LCA_",
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    profile: Literal["quality", "fast"] = "quality"
    autonomy: AutonomyLiteral = "gated"

    llm: LLMSettings = Field(default_factory=LLMSettings)
    search: SearchSettings = Field(default_factory=SearchSettings)
    log: LogSettings = Field(default_factory=LogSettings)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings singleton."""
    return Settings()
