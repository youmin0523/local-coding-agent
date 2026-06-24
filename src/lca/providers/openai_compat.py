"""OpenAI-compatible provider (llama-server, LM Studio, Ollama, …).

Streams ``/v1/chat/completions`` over httpx and reassembles the OpenAI-style
delta stream into our `ChatChunk`s. The fiddly part — turning fragmented
``tool_calls`` deltas back into whole calls, and tolerating engines that send the
arguments as a JSON object instead of a string (llama.cpp #20198) — lives in the
pure, unit-testable `StreamAssembler` so it can be verified without a server.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from lca.core.errors import EngineUnavailableError, ProviderError
from lca.core.messages import ToolCall
from lca.observability.logging import get_logger
from lca.providers.base import (
    ChatChunk,
    ChatRequest,
    ProviderCaps,
    ProviderHealth,
)

log = get_logger("providers.openai_compat")


class _ToolBuf:
    __slots__ = ("args_obj", "args_str", "id", "name")

    def __init__(self) -> None:
        self.id: str | None = None
        self.name: str = ""
        self.args_str: str = ""
        self.args_obj: dict[str, Any] | None = None


class StreamAssembler:
    """Turns a sequence of OpenAI streaming chunks into `ChatChunk`s.

    Pure and synchronous so the reassembly logic can be tested directly.
    """

    def __init__(self) -> None:
        self._tools: dict[int, _ToolBuf] = {}
        self._finished = False

    def feed(self, obj: dict[str, Any]) -> list[ChatChunk]:
        out: list[ChatChunk] = []
        choices = obj.get("choices") or []
        if not choices:
            return out
        choice = choices[0]
        delta = choice.get("delta") or {}

        content = delta.get("content")
        if content:
            out.append(ChatChunk(delta_text=content))

        for tc in delta.get("tool_calls") or []:
            idx = tc.get("index", 0)
            buf = self._tools.setdefault(idx, _ToolBuf())
            if tc.get("id"):
                buf.id = tc["id"]
            fn = tc.get("function") or {}
            if fn.get("name"):
                buf.name += fn["name"]
            args = fn.get("arguments")
            if args is not None:
                if isinstance(args, str):
                    buf.args_str += args
                elif isinstance(args, dict):  # #20198: object instead of string
                    buf.args_obj = args

        finish = choice.get("finish_reason")
        if finish:
            out.extend(self._flush_tools())
            out.append(ChatChunk(finish_reason=finish))
            self._finished = True
        return out

    def finalize(self) -> list[ChatChunk]:
        """Flush any tool calls not closed by an explicit finish_reason."""
        if self._finished:
            return []
        return self._flush_tools()

    def _flush_tools(self) -> list[ChatChunk]:
        out: list[ChatChunk] = []
        for idx in sorted(self._tools):
            buf = self._tools[idx]
            out.append(
                ChatChunk(
                    tool_call=ToolCall(
                        id=buf.id or f"call_{idx}",
                        name=buf.name,
                        arguments=self._parse_args(buf),
                    )
                )
            )
        self._tools.clear()
        return out

    @staticmethod
    def _parse_args(buf: _ToolBuf) -> dict[str, Any]:
        if buf.args_obj is not None:
            return buf.args_obj
        raw = buf.args_str.strip()
        if not raw:
            return {}
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            log.warning("tool_call.args_unparseable", name=buf.name, raw=raw[:200])
            return {}
        return parsed if isinstance(parsed, dict) else {}


class OpenAICompatProvider:
    """A provider for any OpenAI-compatible chat endpoint."""

    name = "openai-compat"

    def __init__(
        self,
        base_url: str,
        api_key: str = "not-needed",
        timeout_s: float = 600.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout_s

    def capabilities(self) -> ProviderCaps:
        return ProviderCaps(
            supports_grammar=False,
            supports_native_tools=True,
            supports_parallel_tool_calls=False,
        )

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"}

    async def health(self) -> ProviderHealth:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{self._base_url}/models", headers=self._headers())
                resp.raise_for_status()
                data = resp.json()
                models = [m.get("id", "") for m in data.get("data", [])]
                return ProviderHealth(reachable=True, models=models)
        except httpx.HTTPError as exc:
            return ProviderHealth(reachable=False, detail=str(exc))

    def _build_body(self, req: ChatRequest) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": req.model,
            "messages": [self._encode_message(m) for m in req.messages],
            "temperature": req.temperature,
            "max_tokens": req.max_tokens,
            "stream": True,
        }
        if req.stop:
            body["stop"] = req.stop
        if req.tools:
            body["tools"] = [{"type": "function", "function": t.model_dump()} for t in req.tools]
            if req.parallel_tool_calls:
                body["parallel_tool_calls"] = True
        return body

    @staticmethod
    def _encode_message(m: Any) -> dict[str, Any]:
        out: dict[str, Any] = {"role": m.role}
        if m.content is not None:
            out["content"] = m.content
        if m.tool_calls:
            out["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)},
                }
                for tc in m.tool_calls
            ]
        if m.tool_call_id:
            out["tool_call_id"] = m.tool_call_id
        if m.name:
            out["name"] = m.name
        return out

    async def chat_stream(self, req: ChatRequest) -> AsyncIterator[ChatChunk]:
        body = self._build_body(req)
        assembler = StreamAssembler()
        try:
            async with (
                httpx.AsyncClient(timeout=self._timeout) as client,
                client.stream(
                    "POST",
                    f"{self._base_url}/chat/completions",
                    headers=self._headers(),
                    json=body,
                ) as resp,
            ):
                if resp.status_code >= 400:
                    text = (await resp.aread()).decode("utf-8", "replace")
                    raise ProviderError(f"engine returned {resp.status_code}: {text[:500]}")
                async for line in resp.aiter_lines():
                    for chunk in self._handle_line(line, assembler):
                        yield chunk
            for chunk in assembler.finalize():
                yield chunk
        except httpx.ConnectError as exc:
            raise EngineUnavailableError(f"cannot reach engine at {self._base_url}: {exc}") from exc
        except httpx.HTTPError as exc:
            raise ProviderError(f"engine request failed: {exc}") from exc

    @staticmethod
    def _handle_line(line: str, assembler: StreamAssembler) -> list[ChatChunk]:
        line = line.strip()
        if not line or not line.startswith("data:"):
            return []
        payload = line[len("data:") :].strip()
        if payload == "[DONE]":
            return []
        try:
            obj = json.loads(payload)
        except json.JSONDecodeError:
            log.warning("stream.bad_json", payload=payload[:200])
            return []
        return assembler.feed(obj)
