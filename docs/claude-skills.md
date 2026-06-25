# Claude Skills (anthropics/skills)

Agent Skills are modular, filesystem-based capabilities that extend Claude. A Skill is a **directory** whose only required file is `SKILL.md` — Markdown with YAML frontmatter plus a Markdown body, optionally bundled with scripts, reference docs, and assets. The same SKILL.md format works across the Claude API, claude.ai, Claude Code, Claude Platform on AWS, and Microsoft Foundry. It is an open standard ("Agent Skills", agentskills.io). Treat Skills like installing software: use only those you authored or got from Anthropic/trusted sources.

## SKILL.md format

A Skill directory's name **must match** the `name` field. Optional sibling dirs:
- `scripts/` — executable code, run via bash; code never enters context, only stdout.
- `references/` — docs loaded on demand (e.g. `REFERENCE.md`, `FORMS.md`).
- `assets/` — templates, images, data files, schemas.

Frontmatter fields:

| Field | Required | Constraints |
|---|---|---|
| `name` | Yes | 1-64 chars; lowercase `a-z`/`0-9`/hyphens; no leading/trailing/consecutive hyphen; no XML tags; not reserved `anthropic`/`claude`; matches dir name. |
| `description` | Yes | 1-1024 chars, non-empty, no XML tags. Primary trigger: state **what** it does AND **when** to use it, third person, with keywords. |
| `license` | No | License name or reference to a bundled license file. |
| `compatibility` | No | <=500 chars; environment requirements (product, packages, network). |
| `metadata` | No | String->string map for client properties; put `version` here (no top-level version field). |
| `allowed-tools` | No | Experimental; space-separated pre-approved tools, e.g. `Bash(git:*) Read`. |

### Frontmatter example

```markdown
---
name: pdf-processing
description: Extract PDF text, fill forms, merge files. Use when handling PDFs.
license: Apache-2.0
metadata:
  author: example-org
  version: "1.0"
---

# PDF Processing
## Instructions
[step-by-step guidance]
## Examples
[concrete input/output examples]
```

Body has no format restrictions; keep it **< 500 lines / ~5k tokens** and push overflow into `references/` files linked **one level deep** with forward-slash paths (reference files >100 lines start with a table of contents). Write descriptions in third person, keyword-rich, on one logical line (wrapping breaks discovery); prefer gerund (`processing-pdfs`) or noun-phrase names. Validate with `skills-ref validate ./my-skill`.

## The official skills list

`github.com/anthropics/skills` (main, verified 2026-06-25) holds a `skills/` dir with **17 skills**, plus `spec/` (points to agentskills.io/specification), `template/`, `.claude-plugin/`, `README.md`, `THIRD_PARTY_NOTICES.md`:

- **algorithmic-art** — generative/p5.js art via an algorithmic-philosophy doc then code.
- **brand-guidelines** — apply Anthropic's official brand colors and typography.
- **canvas-design** — posters/static visual pieces as .png/.pdf.
- **claude-api** — Claude API/SDK reference (model ids, pricing, streaming, tools, MCP, caching); bundled with Claude Code.
- **doc-coauthoring** — 3-stage co-authoring of PRDs, RFCs, specs, proposals.
- **docx** — create/read/edit Word documents.
- **frontend-design** — distinctive, non-templated UI aesthetic direction.
- **internal-comms** — status reports, 3P updates, newsletters, FAQs, incident reports.
- **mcp-builder** — 4-phase build of Python (FastMCP) or Node/TS MCP servers.
- **pdf** — extract/merge/split/fill/OCR PDFs.
- **pptx** — create/read/edit PowerPoint decks.
- **skill-creator** — author/optimize/eval/benchmark Skills (the meta-skill).
- **slack-gif-creator** — Slack-optimized animated GIFs.
- **theme-factory** — apply one of 10 themes (or generate one) to an artifact.
- **web-artifacts-builder** — multi-component React+TS claude.ai artifacts.
- **webapp-testing** — Python Playwright local web-app testing.
- **xlsx** — create/clean/edit spreadsheets.

Only **pptx, xlsx, docx, pdf** are also shipped as **pre-built** Skills referenceable by `skill_id` on the API/claude.ai/AWS/Foundry; **claude-api** ships with Claude Code. All 17 install from the open-source repo into `~/.claude/skills/` or `.claude/skills/`.

## Progressive disclosure (three tiers)

1. **Metadata (~100 tokens, always loaded):** only each installed Skill's `name` + `description` are pre-loaded at startup — so installing many Skills costs almost no context.
2. **Instructions (loaded on activation):** when a request matches a `description`, Claude reads the full `SKILL.md` body via bash (<5k tokens recommended).
3. **Resources (loaded as needed):** bundled `scripts/`/`references/`/`assets/` are read only when referenced; scripts are *executed*, so their code never enters context — effectively unlimited bundled content at zero token cost until used.

## How lca implements a compatible mechanism

The model reproduces because it is structured prompting + filesystem + bash:

1. **Discovery (tier 1):** scan skill dirs for `SKILL.md`, parse YAML frontmatter, inject only `name` + `description` (truncated to a budget) into the system prompt as a lightweight menu.
2. **Triggering:** let the model match on `description` (autonomous) or expose explicit `/name` invocation; formalize with a single `Skill`/`load_skill(name)` tool the model calls.
3. **Progressive disclosure (tiers 2/3):** on invocation read the full body into context; resolve referenced files lazily and **execute** bundled scripts via a shell tool, returning only stdout — keeping code out of context. Keep references one level deep.
4. **Lifecycle:** persist loaded instructions as standing context across turns (re-attach after compaction within a token budget), as Claude Code does.
5. **Tool governance:** layer an allowlist/denylist + approval prompts (equivalent to `allowed-tools`/`disallowed-tools` + permission settings) and gate untrusted skill folders behind an explicit trust step.

The **Claude Agent SDK** is the supported path: set `setting_sources=["user","project"]` (TS `settingSources`) so it discovers filesystem Skills, then filter with the `skills` option (`"all"`, a name list, or `[]`); it auto-adds the `Skill` tool to `allowedTools`. There is **no** programmatic skill-registration API — Skills must be filesystem artifacts — and `allowed-tools` frontmatter is ignored in the SDK/API (control tools via `allowedTools` + `canUseTool` + `permissionMode`).
