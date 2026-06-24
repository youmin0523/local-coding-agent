"""Minimal JSON-Schema → GBNF compiler for *flat* schemas.

llama.cpp can constrain decoding to a GBNF grammar, which makes structurally
invalid output impossible. We deliberately support only flat object schemas
(primitive properties + string enums) and return ``None`` for anything more
complex — both because deep schemas can crash llama.cpp's own converter (#1484)
and because the fallback (native tool calling + Pydantic validation + self-repair)
is safe. Used by the verification judges (forcing verdict JSON) and structured
outputs.
"""

from __future__ import annotations

from typing import Any

_PRIMITIVES = {
    "string": "string",
    "integer": "integer",
    "number": "number",
    "boolean": "boolean",
}

_PREAMBLE = """\
ws ::= [ \\t\\n]*
string ::= "\\"" ( [^"\\\\] | "\\\\" . )* "\\""
integer ::= "-"? [0-9]+
number ::= "-"? [0-9]+ ( "." [0-9]+ )?
boolean ::= "true" | "false"
"""


def _enum_rule(values: list[str]) -> str | None:
    if not all(isinstance(v, str) for v in values):
        return None
    alts = " | ".join('"\\"' + v.replace('"', '\\"') + '\\""' for v in values)
    return f"( {alts} )"


def json_schema_to_gbnf(schema: dict[str, Any]) -> str | None:
    """Compile a flat object schema to GBNF, or return None if unsupported."""
    if schema.get("type") != "object":
        return None
    properties = schema.get("properties")
    if not isinstance(properties, dict) or not properties:
        return None

    parts: list[str] = []
    for key, prop in properties.items():
        if not isinstance(prop, dict):
            return None
        if "enum" in prop:
            rule = _enum_rule(list(prop["enum"]))
            if rule is None:
                return None
        else:
            ptype = prop.get("type")
            if ptype not in _PRIMITIVES:
                return None  # nested objects/arrays unsupported → fall back
            rule = _PRIMITIVES[ptype]
        key_literal = '"\\"' + key.replace('"', '\\"') + '\\""'
        parts.append(f'{key_literal} ws ":" ws {rule}')

    body = ' ws "," ws '.join(parts)
    root = f'root ::= "{{" ws {body} ws "}}"'
    return f"{root}\n{_PREAMBLE}"
