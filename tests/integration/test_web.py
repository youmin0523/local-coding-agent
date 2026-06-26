"""Web backend: SSE run streaming, tool execution, and approval resolution."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from lca.core.agent import Agent
from lca.permissions.policy import DefaultPolicy
from lca.providers.fake import FakeProvider, text_chunks, tool_chunks
from lca.tools import build_default_registry
from lca.web.approver import WebApprover
from lca.web.server import create_app


def _collect(client: TestClient, run_id: str) -> list[dict]:
    events: list[dict] = []
    with client.stream("GET", f"/api/runs/{run_id}/events") as resp:
        for line in resp.iter_lines():
            text = line if isinstance(line, str) else line.decode()
            if text.startswith("data:"):
                ev = json.loads(text[len("data:") :].strip())
                events.append(ev)
                if ev.get("type") == "turn_finished":
                    break
    return events


def test_run_streams_tokens_and_finishes(tmp_path: Path):
    def builder(approver, message):
        return Agent(
            FakeProvider([text_chunks("Hello from lca.")]),
            build_default_registry(enable_web=False),
            DefaultPolicy(),
            approver,
            model="fake",
        )

    client = TestClient(create_app(workspace=tmp_path, agent_builder=builder))
    run_id = client.post("/api/runs", json={"message": "hi", "mode": "gated"}).json()["run_id"]
    events = _collect(client, run_id)
    text = "".join(e["text"] for e in events if e["type"] == "token")
    assert "Hello from lca" in text
    assert events[-1]["type"] == "turn_finished"


def test_autonomous_run_executes_tool_via_web(tmp_path: Path):
    def builder(approver, message):
        return Agent(
            FakeProvider(
                [
                    tool_chunks("write_file", {"path": "w.txt", "content": "data"}, "c1"),
                    text_chunks("done"),
                ]
            ),
            build_default_registry(enable_web=False),
            DefaultPolicy(),
            approver,
            model="fake",
        )

    client = TestClient(create_app(workspace=tmp_path, agent_builder=builder))
    run_id = client.post("/api/runs", json={"message": "write it", "mode": "autonomous"}).json()[
        "run_id"
    ]
    events = _collect(client, run_id)
    assert any(e["type"] == "tool_finished" and e["name"] == "write_file" for e in events)
    assert (tmp_path / "w.txt").read_text() == "data"


def test_approval_endpoint_unknown_id_returns_false(tmp_path: Path):
    client = TestClient(create_app(workspace=tmp_path, agent_builder=lambda a, m: _noop_agent(a)))
    resp = client.post("/api/approvals/nope", json={"approved": True})
    assert resp.json() == {"resolved": False}


def test_events_unknown_run_404(tmp_path: Path):
    client = TestClient(create_app(workspace=tmp_path, agent_builder=lambda a, m: _noop_agent(a)))
    assert client.get("/api/runs/nope/events").status_code == 404


def test_stop_unknown_run_returns_false(tmp_path: Path):
    client = TestClient(create_app(workspace=tmp_path, agent_builder=lambda a, m: _noop_agent(a)))
    assert client.post("/api/runs/nope/stop").json() == {"stopped": False}


def test_index_html_served_with_new_ui(tmp_path: Path):
    client = TestClient(create_app(workspace=tmp_path, agent_builder=lambda a, m: _noop_agent(a)))
    r = client.get("/")
    assert r.status_code == 200
    # the rewritten UI: conversation sidebar, stop button, markdown export, context gauge
    for marker in ('id="convList"', 'id="stop"', 'id="copyMd"', 'id="ctx"', "sendMessage"):
        assert marker in r.text


def _noop_agent(approver) -> Agent:
    return Agent(
        FakeProvider([text_chunks("ok")]),
        build_default_registry(enable_web=False),
        DefaultPolicy(),
        approver,
        model="fake",
    )


def test_conversation_crud(tmp_path: Path):
    client = TestClient(create_app(workspace=tmp_path, agent_builder=lambda a, m: _noop_agent(a)))
    # a default conversation exists on startup
    assert len(client.get("/api/conversations").json()["conversations"]) >= 1
    cid = client.post("/api/conversations", json={"title": "work"}).json()["id"]
    titles = [c["title"] for c in client.get("/api/conversations").json()["conversations"]]
    assert "work" in titles
    assert client.get(f"/api/conversations/{cid}").json()["messages"] == []  # new = empty
    assert client.delete(f"/api/conversations/{cid}").json()["deleted"] is True
    titles = [c["title"] for c in client.get("/api/conversations").json()["conversations"]]
    assert "work" not in titles
    # persistence directory is created
    assert (tmp_path / ".lca" / "conversations").is_dir()


def test_run_titles_and_records_conversation(tmp_path: Path):
    def builder(approver, message):
        return Agent(
            FakeProvider([text_chunks("hello from lca")]),
            build_default_registry(enable_web=False),
            DefaultPolicy(),
            approver,
            model="fake",
        )

    client = TestClient(create_app(workspace=tmp_path, agent_builder=builder))
    resp = client.post("/api/runs", json={"message": "fix the parser", "mode": "gated"}).json()
    cid = resp["conversation_id"]
    assert cid and resp["token_budget"]
    _collect(client, resp["run_id"])
    # the conversation is titled from the first message and records both turns
    msgs = client.get(f"/api/conversations/{cid}").json()["messages"]
    assert any(m["role"] == "user" and "fix the parser" in m["content"] for m in msgs)
    assert any(m["role"] == "assistant" and "hello from lca" in m["content"] for m in msgs)
    titles = [c["title"] for c in client.get("/api/conversations").json()["conversations"]]
    assert any("fix the parser" in t for t in titles)


@pytest.mark.asyncio
async def test_web_approver_request_resolve():
    import asyncio

    from lca.core.messages import ToolCall
    from lca.tools.base import RiskLevel

    approver = WebApprover()
    call = ToolCall(id="req1", name="write_file", arguments={})
    task = asyncio.create_task(approver.request(call, RiskLevel.WRITE))
    await asyncio.sleep(0)  # let request register the future
    assert approver.resolve("req1", True) is True
    assert await task is True
