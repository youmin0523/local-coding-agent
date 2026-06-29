"""Engine auto-detection: validate the /models body, reject stray services, fail to None."""

from __future__ import annotations

import lca.providers.registry as reg
from lca.providers.registry import detect_base_url


class _Resp:
    def __init__(self, status: int, body: object) -> None:
        self.status_code = status
        self._body = body

    def json(self) -> object:
        return self._body


def test_detect_returns_first_valid_openai_models_endpoint(monkeypatch):
    def fake_get(url, **kw):
        if "1234" in url:  # only LM Studio answers with a proper /models body
            return _Resp(200, {"object": "list", "data": [{"id": "m"}]})
        raise ConnectionError("down")

    monkeypatch.setattr(reg.httpx, "get", fake_get)
    assert detect_base_url("http://127.0.0.1:8080/v1") == "http://127.0.0.1:1234/v1"


def test_detect_rejects_stray_non_llm_service(monkeypatch):
    # a service returns 200 but not an OpenAI models shape → must NOT be chosen
    monkeypatch.setattr(reg.httpx, "get", lambda url, **kw: _Resp(200, {"hello": "world"}))
    assert detect_base_url("http://127.0.0.1:8080/v1") is None


def test_detect_rejects_4xx_even_with_data(monkeypatch):
    monkeypatch.setattr(reg.httpx, "get", lambda url, **kw: _Resp(401, {"data": []}))
    assert detect_base_url("http://127.0.0.1:8080/v1") is None


def test_detect_returns_none_when_nothing_answers(monkeypatch):
    def boom(url, **kw):
        raise ConnectionError("refused")

    monkeypatch.setattr(reg.httpx, "get", boom)
    assert detect_base_url("http://127.0.0.1:8080/v1") is None
