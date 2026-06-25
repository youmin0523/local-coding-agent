"""Skill loading (SKILL.md parsing, validation, progressive disclosure) + use_skill tool."""

from __future__ import annotations

from pathlib import Path

from lca.core.session import Session
from lca.permissions.approver import AutoApprover
from lca.skills.loader import bundled_dir, load_skills, parse_skill, skills_index
from lca.tools.base import ToolContext
from lca.tools.skill import UseSkillTool


def _write_skill(root: Path, name: str, frontmatter: str, body: str = "Do the thing.") -> Path:
    d = root / name
    d.mkdir(parents=True)
    p = d / "SKILL.md"
    p.write_text(f"---\n{frontmatter}\n---\n\n{body}\n", "utf-8")
    return p


def test_parse_valid_skill(tmp_path: Path):
    p = _write_skill(
        tmp_path,
        "make-thing",
        "name: make-thing\ndescription: Make a thing. Use when asked to make things.\n"
        'metadata:\n  version: "2.0"',
    )
    skill = parse_skill(p)
    assert skill is not None
    assert skill.name == "make-thing"
    assert "Make a thing" in skill.description
    assert skill.metadata["version"] == "2.0"
    assert "Do the thing" in skill.body


def test_invalid_names_rejected(tmp_path: Path):
    bad = _write_skill(tmp_path, "Bad_Name", "name: Bad_Name\ndescription: x")
    assert parse_skill(bad) is None  # uppercase/underscore
    reserved = _write_skill(tmp_path, "claude-helper", "name: claude-helper\ndescription: x")
    assert parse_skill(reserved) is None  # reserved word


def test_load_skills_and_index(tmp_path: Path):
    _write_skill(tmp_path, "alpha", "name: alpha\ndescription: First skill.")
    _write_skill(tmp_path, "beta", "name: beta\ndescription: Second skill.")
    skills = load_skills(tmp_path)
    assert [s.name for s in skills] == ["alpha", "beta"]
    idx = skills_index(skills)
    assert "alpha: First skill." in idx
    assert "use_skill" in idx


def test_bundled_skills_present():
    skills = load_skills(bundled_dir())
    names = {s.name for s in skills}
    assert {"normalized-postgres-schema", "secure-fastapi-endpoint"} <= names


async def test_use_skill_tool(tmp_path: Path):
    _write_skill(tmp_path, "alpha", "name: alpha\ndescription: First.", body="STEP ONE")
    skills = load_skills(tmp_path)
    tool = UseSkillTool(skills)
    ctx = ToolContext(
        workspace_root=tmp_path, approver=AutoApprover(), session=Session(workspace_root=tmp_path)
    )
    res = await tool.run({"name": "alpha"}, ctx)
    assert res.ok and "STEP ONE" in res.content
    miss = await tool.run({"name": "nope"}, ctx)
    assert not miss.ok and "unknown skill" in miss.content
