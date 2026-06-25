"""`use_skill` — load a skill's full instructions on demand (progressive disclosure).

The agent sees only skill names + descriptions in its system prompt; when a task
matches one, it calls this tool with the skill name to pull the SKILL.md body into
context (and a note about any bundled resources). Read-only.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from lca.skills.loader import Skill
from lca.tools.base import RiskLevel, ToolContext, ToolResult, ToolSpec


class UseSkillTool:
    spec = ToolSpec(
        name="use_skill",
        description=(
            "Load the full instructions for an available skill by name (see the skills list "
            "in the system prompt). Call this before performing a task the skill covers."
        ),
        parameters={
            "type": "object",
            "properties": {"name": {"type": "string", "description": "The skill's name."}},
            "required": ["name"],
        },
        risk=RiskLevel.READ,
    )

    def __init__(self, skills: Sequence[Skill]) -> None:
        self._by_name = {s.name: s for s in skills}

    async def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        name = str(args.get("name", "")).strip()
        skill = self._by_name.get(name)
        if skill is None:
            available = ", ".join(sorted(self._by_name)) or "(none installed)"
            return ToolResult.error(f"unknown skill '{name}'. Available: {available}")
        header = f"# Skill: {skill.name}\n{skill.description}\n"
        resources = skill.path.parent
        extras = sorted(p.name for p in resources.iterdir() if p.name != "SKILL.md")
        if extras:
            header += f"\nBundled resources in this skill's directory: {', '.join(extras)}\n"
        return ToolResult.ok_text(f"{header}\n---\n{skill.body}")
