"""doctor: GPU parsing and the model-mismatch warning."""

from __future__ import annotations

from lca.config.settings import LLMSettings, Settings
from lca.engine_mgmt.doctor import run_doctor
from lca.providers.base import ProviderCaps, ProviderHealth


class _StubProvider:
    name = "stub"

    def __init__(self, models: list[str]) -> None:
        self._models = models

    def capabilities(self) -> ProviderCaps:
        return ProviderCaps()

    async def health(self) -> ProviderHealth:
        return ProviderHealth(reachable=True, models=self._models)


async def test_warns_when_active_model_not_served():
    settings = Settings(profile="fast", llm=LLMSettings(fast_model="qwen2.5-coder-7b-instruct"))
    report = await run_doctor(settings, _StubProvider(models=["some-other-model"]))
    assert report.engine.reachable
    assert any("not served by the engine" in w for w in report.warnings)


async def test_no_warning_when_model_matches():
    settings = Settings(profile="fast", llm=LLMSettings(fast_model="qwen2.5-coder-7b-instruct"))
    report = await run_doctor(settings, _StubProvider(models=["qwen2.5-coder-7b-instruct"]))
    assert not any("not served" in w for w in report.warnings)
