"""Load Agent Skills (SKILL.md) — the Anthropic/Claude skills format, locally.

A *skill* is a directory containing a ``SKILL.md`` file: YAML frontmatter (at
least ``name`` + ``description``) followed by a Markdown body of instructions.
Mirrors the official spec (anthropics/skills): the directory name matches
``name``; ``name`` is 1-64 chars of lowercase/digits/hyphens (no leading/trailing
or doubled hyphen, and not the reserved words "anthropic"/"claude"); the
``description`` (1-1024 chars) is the trigger text.

Progressive disclosure, tier 1: only ``name`` + ``description`` of every skill is
injected into the system prompt (see :func:`skills_index`). The full body is
pulled into context on demand by the ``use_skill`` tool — cheap to install many.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import structlog

log = structlog.get_logger(__name__)

_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_RESERVED = ("anthropic", "claude")
_MAX_NAME = 64
_MAX_DESC = 1024


@dataclass(frozen=True)
class Skill:
    """A loaded skill: its trigger metadata plus the full instruction body."""

    name: str
    description: str
    body: str
    path: Path
    allowed_tools: tuple[str, ...] = ()
    license: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)


def _valid_name(name: str) -> bool:
    return (
        1 <= len(name) <= _MAX_NAME
        and bool(_NAME_RE.match(name))
        and not any(r in name for r in _RESERVED)
    )


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def _split_frontmatter(text: str) -> tuple[dict[str, object], str]:
    """Parse leading ``---`` YAML frontmatter (flat keys + one nested ``metadata``)."""
    if not text.startswith("---"):
        return {}, text.strip()
    lines = text.splitlines()
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        return {}, text.strip()
    body = "\n".join(lines[end + 1 :]).strip()
    data: dict[str, object] = {}
    nested_key: str | None = None
    for raw in lines[1:end]:
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if raw[0] in " \t" and nested_key:  # indented → part of the current nested block
            k, _, v = raw.strip().partition(":")
            block = data.get(nested_key)
            if k and isinstance(block, dict):
                block[k.strip()] = _unquote(v)
            continue
        key, _, value = raw.partition(":")
        key, value = key.strip(), value.strip()
        if not key:
            continue
        if value == "":
            nested_key = key
            data[key] = {}
        else:
            nested_key = None
            data[key] = _unquote(value)
    return data, body


def parse_skill(skill_md: Path) -> Skill | None:
    """Parse one SKILL.md; return None (and log) if missing required/valid fields."""
    try:
        text = skill_md.read_text("utf-8")
    except OSError as exc:
        log.warning("skills.read_failed", path=str(skill_md), error=str(exc))
        return None
    fm, body = _split_frontmatter(text)
    name = str(fm.get("name", "")).strip()
    description = str(fm.get("description", "")).strip()
    if not _valid_name(name):
        log.warning("skills.invalid_name", path=str(skill_md), name=name)
        return None
    if not (1 <= len(description) <= _MAX_DESC):
        log.warning("skills.invalid_description", path=str(skill_md), name=name)
        return None
    if name != skill_md.parent.name:
        log.warning("skills.name_dir_mismatch", path=str(skill_md), name=name)
    meta_raw = fm.get("metadata")
    metadata = {str(k): str(v) for k, v in meta_raw.items()} if isinstance(meta_raw, dict) else {}
    tools_raw = str(fm.get("allowed-tools", "")).split()
    return Skill(
        name=name,
        description=description,
        body=body,
        path=skill_md,
        allowed_tools=tuple(tools_raw),
        license=str(fm["license"]) if "license" in fm else None,
        metadata=metadata,
    )


def load_skills(*roots: Path) -> list[Skill]:
    """Discover ``<root>/<skill-name>/SKILL.md`` across roots; first name wins."""
    found: dict[str, Skill] = {}
    for root in roots:
        if not root.is_dir():
            continue
        for skill_md in sorted(root.glob("*/SKILL.md")):
            skill = parse_skill(skill_md)
            if skill and skill.name not in found:
                found[skill.name] = skill
    return sorted(found.values(), key=lambda s: s.name)


def skills_index(skills: list[Skill]) -> str:
    """Tier-1 metadata block listing name+description of every installed skill."""
    if not skills:
        return ""
    lines = "\n".join(f"- {s.name}: {s.description}" for s in skills)
    return (
        "Available skills — when a request matches one, call the `use_skill` tool with its "
        "name to load full instructions BEFORE doing the work:\n" + lines
    )


def bundled_dir() -> Path:
    """The skills shipped inside the lca package."""
    return Path(__file__).parent / "bundled"


def default_skill_roots() -> list[Path]:
    """Bundled skills, plus a ``skills/`` directory in the current workspace."""
    return [bundled_dir(), Path.cwd() / "skills"]
