# lca — demo walkthrough

A real, captured run of the agent on the target machine (RTX 5070 Laptop, 8 GB).
Everything here is **100% local** — the model (Qwen running in LM Studio), the
verification, and the UI all live on-device; nothing leaves the machine.

The screenshots below are from `lca web`; the same agent is available from the CLI.

---

## 0. Engine ready — `lca doctor`

lca talks to a local OpenAI-compatible server. Point it at the engine and check:

```console
$ setx LCA_LLM__BASE_URL "http://127.0.0.1:1234/v1"   # LM Studio's port
$ uv run lca doctor
                                  lca doctor
┌──────────────────────────────┬──────────────────────────────────────────────┐
│ GPU · NVIDIA RTX 5070 Laptop  │ 2067/8151 MB free · driver 592.27              │
│ Discrete GPU                  │ present                                        │
│ Engine                        │ reachable (qwen3-coder-30b-a3b-instruct,       │
│                               │ qwen2.5-coder-7b-instruct, nomic-embed-text)   │
│ Context budget                │ 16384 tokens                                   │
└──────────────────────────────┴──────────────────────────────────────────────┘
┌─ Verdict ─┐
│ READY     │
└───────────┘
```

## 1. Open the web UI — `lca web`

```console
$ uv run lca web -C ./my-project
lca web → http://127.0.0.1:8765
```

A clean, dark chat UI. The header shows it's verification-grounded and 100% local;
the **mode** selector switches between `gated` (ask before writing/running),
`autonomous` (auto-approve up to the risk ceiling), and `plan` (propose only).

![landing](demo-assets/01-landing.png)

## 2. Ask a question — streamed answer, then verified

Type a question and press Enter. The answer streams token-by-token and renders
Markdown. When the turn is grounded, a green **verification badge** appears — the
agent only delivers what it can stand behind.

![q&a](demo-assets/02-qa.png)

## 3. Autonomous coding — tools in real time

Switch **mode → autonomous** and ask it to write and run a script. The agent calls
its tools live: here `write_file` creates `palindrome.py` (shown as a colored diff
card), with the Send button disabled while the turn is in flight.

![working](demo-assets/03-working.png)

## 4. Execution-grounded verification

It then runs the file with `run_python`, reads the real output, and finishes with
**`verified: pass — grounded by executed code`**. The verdict comes from actually
executing the code, not from the model's own say-so — this is the anti-hallucination
core: execution is the oracle.

![done](demo-assets/04-done.png)

---

## Same thing from the CLI

```bash
uv run lca ask "add a /health endpoint and a test, then run pytest" --auto --verify
uv run lca ask "explain the auth flow in this repo"            # RAG-grounded, cites file:line
uv run lca ask "summarize this build log" -C ./proj --copy     # answer copied to clipboard
uv run lca ask "deployment checklist" --md deploy.md           # answer saved as markdown
uv run lca chat                                                # multi-turn session
uv run lca skills                                              # the 11 bundled Agent Skills
```

See [`usage.md`](usage.md) for the full command reference and flags.

> Notes: the brain model (30B) is used when `LCA_PROFILE=quality`; otherwise the
> fast 7B handles easy turns and escalates verification by difficulty. The web and
> CLI build the agent through the same composition root, so behavior is identical.
