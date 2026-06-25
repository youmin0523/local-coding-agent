# Using lca

A practical walkthrough: start the engine, then drive the agent from the CLI or
the browser. All commands run from the repo root via `uv run`.

## 0. One-time setup

```bash
uv sync                       # base install (Python 3.12+, uv)
uv sync --extra rag --extra web --extra search --extra mcp   # features you want
uv sync --extra browser && uv run playwright install chromium  # browser tools (optional)
uv sync --extra office        # Word/PowerPoint/Excel generation (optional)
```

## 1. Start the inference engine (required)

lca talks to a local OpenAI-compatible server. With **LM Studio**: load a model
(`qwen2.5-coder-7b-instruct`, and `qwen3-coder-30b-a3b-instruct` for the brain),
then start its local server.

**Endpoint:** lca defaults to `http://127.0.0.1:8080/v1`, but LM Studio serves on
`:1234`. Point lca at it (either set the env var, or change LM Studio's port):

```bash
# PowerShell (persists for new terminals):
setx LCA_LLM__BASE_URL "http://127.0.0.1:1234/v1"
setx LCA_PROFILE "quality"     # use the 30B brain; omit/"fast" to stay on the 7B
# open a NEW terminal so the vars take effect
```

Verify before relying on it:

```bash
uv run lca doctor              # GPU + engine reachability; prints READY / NOT READY
uv run lca config              # the effective endpoint, models, profile, autonomy
```

`doctor` says **NOT READY** until the engine endpoint is reachable.

## 2. Index your code (for repo-aware answers)

```bash
uv run lca index .             # build the RAG index so answers cite file:line
uv run lca stats               # indexed chunks + learned experiences
```

## 3. Ask it to do things

```bash
uv run lca ask "create hello.py that prints the date and run it"
uv run lca ask "explain the JWT auth flow in this repo"
uv run lca chat                # multi-turn session (Ctrl-D / 'exit' to quit)
uv run lca web                 # browser UI at http://127.0.0.1:8765
```

### Useful `ask` flags

| Flag | Effect |
|---|---|
| `--auto` | Autonomous: auto-approve actions up to the risk ceiling (no y/n prompts). |
| `--plan` | Plan only — propose actions, never execute. |
| `--verify` | Verify the final answer (deliver-or-abstain; best-of-N). |
| `--no-route` | Don't auto-pick model/verification by difficulty. |
| `--mcp` | Connect local MCP servers (filesystem/git/fetch). |
| `--copy` | Copy the final answer to the clipboard. |
| `--md FILE` | Also save the final answer to a `.md` file. |
| `-C DIR` | Run against another workspace directory. |

Examples:

```bash
uv run lca ask "add a /health endpoint and a test, then run pytest" --auto --verify
uv run lca ask "summarize this build log" -C ./myproject --copy
uv run lca ask "give me a deployment checklist as markdown" --md deploy.md
```

By default the agent is **gated**: it asks before writing files or running shell
commands. Use `--auto` for hands-off runs.

## 4. Skills

```bash
uv run lca skills              # list installed Agent Skills (SKILL.md)
```

When a request matches a skill's description, the agent loads that skill's
instructions automatically (via the `use_skill` tool). Bundled skills cover
normalized schemas, secure FastAPI endpoints, accessible React components, log
triage, debugging, deployment, Word/PowerPoint/Excel generation, Markdown, and
diagrams. Add your own at `<workspace>/skills/<name>/SKILL.md`.

## 5. Other commands

```bash
uv run lca mcp                 # list connected MCP tools
uv run lca learn               # self-improvement loop (rollout -> reward -> SFT corpus)
uv run lca eval                # run the eval suite and print a scorecard
```

## Troubleshooting

- **`doctor` says NOT READY / "Engine unreachable"** — the server isn't running or
  the port is wrong. Start LM Studio's server and set `LCA_LLM__BASE_URL`.
- **Answers stay on the 7B model** — set `LCA_PROFILE=quality` and load the 30B.
- **It keeps asking for approval** — that's the default gated mode; pass `--auto`.
