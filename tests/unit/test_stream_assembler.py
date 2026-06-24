"""The provider stream reassembly, including the llama.cpp #20198 footgun."""

from __future__ import annotations

from lca.providers.openai_compat import StreamAssembler


def _drain(assembler: StreamAssembler, objs: list[dict]) -> list:
    out = []
    for obj in objs:
        out.extend(assembler.feed(obj))
    out.extend(assembler.finalize())
    return out


def test_text_streaming():
    asm = StreamAssembler()
    chunks = _drain(
        asm,
        [
            {"choices": [{"delta": {"content": "Hel"}}]},
            {"choices": [{"delta": {"content": "lo"}}]},
            {"choices": [{"delta": {}, "finish_reason": "stop"}]},
        ],
    )
    text = "".join(c.delta_text for c in chunks if c.delta_text)
    assert text == "Hello"
    assert any(c.finish_reason == "stop" for c in chunks)


def test_tool_call_arguments_as_streamed_string():
    asm = StreamAssembler()
    chunks = _drain(
        asm,
        [
            {
                "choices": [
                    {
                        "delta": {
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "id": "call_1",
                                    "function": {"name": "read_file", "arguments": '{"pa'},
                                }
                            ]
                        }
                    }
                ]
            },
            {
                "choices": [
                    {
                        "delta": {
                            "tool_calls": [{"index": 0, "function": {"arguments": 'th": "a.py"}'}}]
                        }
                    }
                ]
            },
            {"choices": [{"delta": {}, "finish_reason": "tool_calls"}]},
        ],
    )
    calls = [c.tool_call for c in chunks if c.tool_call]
    assert len(calls) == 1
    assert calls[0].name == "read_file"
    assert calls[0].arguments == {"path": "a.py"}


def test_tool_call_arguments_as_object_20198():
    # llama.cpp sometimes emits arguments as a JSON object, not a string.
    asm = StreamAssembler()
    chunks = _drain(
        asm,
        [
            {
                "choices": [
                    {
                        "delta": {
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "id": "c1",
                                    "function": {"name": "x", "arguments": {"a": 1, "b": "y"}},
                                }
                            ]
                        }
                    }
                ]
            },
            {"choices": [{"delta": {}, "finish_reason": "tool_calls"}]},
        ],
    )
    calls = [c.tool_call for c in chunks if c.tool_call]
    assert calls[0].arguments == {"a": 1, "b": "y"}


def test_unparseable_arguments_degrade_to_empty():
    asm = StreamAssembler()
    chunks = _drain(
        asm,
        [
            {
                "choices": [
                    {
                        "delta": {
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "id": "c",
                                    "function": {"name": "t", "arguments": "{not json"},
                                }
                            ]
                        }
                    }
                ]
            },
            {"choices": [{"delta": {}, "finish_reason": "tool_calls"}]},
        ],
    )
    calls = [c.tool_call for c in chunks if c.tool_call]
    assert calls[0].arguments == {}
