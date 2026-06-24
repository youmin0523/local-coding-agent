"""GBNF generation for flat schemas, with safe fallback on complex ones."""

from __future__ import annotations

from lca.providers.grammar import json_schema_to_gbnf


def test_flat_schema_with_enum_and_primitives():
    schema = {
        "type": "object",
        "properties": {
            "verdict": {"enum": ["pass", "fail", "uncertain"]},
            "confidence": {"type": "number"},
            "note": {"type": "string"},
        },
    }
    grammar = json_schema_to_gbnf(schema)
    assert grammar is not None
    assert "root ::=" in grammar
    assert '\\"verdict\\"' in grammar
    assert '\\"pass\\"' in grammar and '\\"fail\\"' in grammar
    assert "number" in grammar and "string" in grammar


def test_nested_schema_falls_back_to_none():
    schema = {
        "type": "object",
        "properties": {"inner": {"type": "object", "properties": {"x": {"type": "string"}}}},
    }
    assert json_schema_to_gbnf(schema) is None


def test_array_schema_falls_back_to_none():
    schema = {"type": "object", "properties": {"items": {"type": "array"}}}
    assert json_schema_to_gbnf(schema) is None


def test_non_object_returns_none():
    assert json_schema_to_gbnf({"type": "string"}) is None
    assert json_schema_to_gbnf({"type": "object", "properties": {}}) is None
