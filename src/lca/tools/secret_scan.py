"""`secret_scan` — find hardcoded secrets and audit .gitignore.

A `RiskLevel.READ` tool that enforces two hygiene rules the user cares about:
no API keys / tokens / passwords hardcoded in source (they belong in env), and a
`.gitignore` that actually excludes secrets and noise. It is grep-grade and
deliberately conservative: usages that read from the environment (os.environ,
process.env, settings.*) and obvious placeholders are not flagged.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from lca.tools.base import RiskLevel, ToolContext, ToolResult, ToolSpec
from lca.tools.fs_read import _looks_binary
from lca.tools.util import to_rel

_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("anthropic_key", re.compile(r"sk-ant-[A-Za-z0-9_\-]{16,}")),
    ("openai_key", re.compile(r"sk-(?:proj-)?[A-Za-z0-9]{20,}")),
    ("aws_access_key_id", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("github_token", re.compile(r"gh[posru]_[A-Za-z0-9]{30,}")),
    ("slack_token", re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}")),
    ("google_api_key", re.compile(r"AIza[0-9A-Za-z_\-]{30,}")),
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("jwt", re.compile(r"eyJ[A-Za-z0-9_\-]{8,}\.eyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}")),
    (
        "hardcoded_secret_assignment",
        re.compile(
            r"""(?i)\b(api[_-]?key|secret|token|password|passwd|pwd|access[_-]?key|"""
            r"""client[_-]?secret)\b\s*[:=]\s*['"]([^'"]{6,})['"]"""
        ),
    ),
]
# Values that are clearly not real secrets.
_PLACEHOLDER = re.compile(
    r"(?i)(your|example|placeholder|change[_-]?me|dummy|sample|test|none|not[-_ ]?needed|"
    r"redacted|xxx+|\*{3,}|\$\{|<[^>]+>|\{\{)"
)
# Lines that correctly source secrets from the environment/config (not a leak).
_ENV_USE = re.compile(
    r"(os\.environ|os\.getenv|getenv|process\.env|import\.meta\.env|"
    r"\bsettings\.|\bconfig\.|Field\(|SecretStr|BaseSettings)"
)
_CODE_SUFFIXES = {
    ".py",
    ".pyi",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".go",
    ".rs",
    ".java",
    ".rb",
    ".php",
    ".cs",
    ".sh",
    ".ps1",
    ".yaml",
    ".yml",
    ".toml",
    ".json",
    ".ini",
    ".cfg",
    ".env",
}
_SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
    "dist",
    "build",
    "data",
    "models",
}
_RECOMMENDED_GITIGNORE = [".env", "*.pem", "*.key", "__pycache__/", ".venv/", "node_modules/"]
_MAX_FINDINGS = 100


def scan_text(text: str) -> list[tuple[int, str]]:
    """Return ``(line_number, secret_type)`` for each likely hardcoded secret.

    Conservative: lines that read from the environment/config and obvious
    placeholders are skipped. Shared by the ``secret_scan`` tool and the write
    tools (which warn the instant they persist a secret).
    """
    hits: list[tuple[int, str]] = []
    for i, line in enumerate(text.splitlines(), 1):
        if _ENV_USE.search(line):
            continue
        for name, pat in _PATTERNS:
            m = pat.search(line)
            if not m:
                continue
            value = m.group(m.lastindex or 0)
            if _PLACEHOLDER.search(value):
                continue
            hits.append((i, name))
            break
    return hits


class SecretScanTool:
    spec = ToolSpec(
        name="secret_scan",
        description=(
            "Scan the workspace for hardcoded secrets (API keys, tokens, passwords, private "
            "keys) that should be in environment variables, and audit .gitignore for missing "
            "sensitive entries. Read-only."
        ),
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Subpath to scan; defaults to root."}
            },
        },
        risk=RiskLevel.READ,
    )

    async def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        root = ctx.workspace_root.resolve()
        scan_root = root / str(args.get("path", ".")) if args.get("path") else root
        findings = self._scan_secrets(root, scan_root)
        gitignore = self._audit_gitignore(root)

        lines: list[str] = []
        if findings:
            lines.append(f"⚠ {len(findings)} possible hardcoded secret(s):")
            lines.extend(findings)
        else:
            lines.append("✓ No hardcoded secrets detected.")
        lines.append("")
        lines.extend(gitignore)
        ok = not findings
        return ToolResult(ok=ok, content="\n".join(lines))

    def _scan_secrets(self, root: Path, scan_root: Path) -> list[str]:
        out: list[str] = []
        for path in sorted(scan_root.rglob("*")):
            if not path.is_file() or any(p in _SKIP_DIRS for p in path.parts):
                continue
            if path.suffix.lower() not in _CODE_SUFFIXES or _looks_binary(path):
                continue
            # .env / .env.* legitimately hold secrets; never flag their contents.
            if path.name == ".env" or path.name.startswith(".env."):
                continue
            try:
                text = path.read_text("utf-8", errors="replace")
            except OSError:
                continue
            for line_no, name in scan_text(text):
                out.append(f"  {to_rel(root, path)}:{line_no}: {name}")
                if len(out) >= _MAX_FINDINGS:
                    out.append("  …[truncated]")
                    return out
        return out

    def _audit_gitignore(self, root: Path) -> list[str]:
        gi = root / ".gitignore"
        env_present = (root / ".env").exists()
        if not gi.is_file():
            msg = [
                "✗ No .gitignore found. Create one ignoring at least: "
                + ", ".join(_RECOMMENDED_GITIGNORE)
            ]
            if env_present:
                msg.append("  ⚠ a .env file exists and is NOT ignored — add `.env` immediately.")
            return msg
        content = gi.read_text("utf-8", errors="replace")
        missing = [e for e in _RECOMMENDED_GITIGNORE if e.rstrip("/") not in content]
        out: list[str] = []
        if missing:
            out.append("△ .gitignore is missing recommended entries: " + ", ".join(missing))
        else:
            out.append("✓ .gitignore covers the common sensitive/noise entries.")
        if env_present and ".env" in missing:
            out.append("  ⚠ a .env file exists but `.env` is not ignored — add it now.")
        return out
