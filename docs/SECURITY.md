# Security & threat model

lca exists *because* of security: it runs entirely on-device so code never leaves
the machine. But the agent executes **untrusted model output** against your files
and shell, so the harness treats the model as an adversary and contains it.

## Threat model
- **Untrusted:** everything the model emits (tool calls, arguments, code, shell).
- **Trusted:** the user, the lca code, and the local OS.
- **Goal:** the model cannot read/modify anything outside the chosen workspace,
  cannot run arbitrary host commands unattended, and cannot exfiltrate data —
  unless the user explicitly allows it.

## Defenses (in depth)
1. **Workspace jail.** Every file path goes through `safe_resolve`, which rejects
   `..` traversal and absolute paths outside the workspace root (tested
   adversarially). Read/write/edit/search/symbols cannot escape it.
2. **Permission gate.** READ is free; WRITE / SHELL / NETWORK require approval in
   the default `gated` mode. `autonomous` mode auto-approves only up to a
   configurable risk ceiling; `plan` mode never executes side effects.
3. **Allowlisted shell, no shell interpreter.** `run_shell` only accepts an
   allowlisted executable, and commands run via `create_subprocess_exec` — **not**
   through a shell — so metacharacters (`;`, `&&`, `|`, backticks) are passed as
   literal args and are never interpreted. Injection via chaining is structurally
   impossible.
4. **Sandboxed execution.** Commands/code run with a hard wall-clock timeout, a
   **scrubbed environment** (only PATH/TEMP/… are passed; parent-process secrets
   are dropped), and a fixed working directory. `run_python` additionally disables
   network by default and runs the snippet from a private temp dir.
5. **MCP scoping.** MCP servers are launched per the declared config; the
   filesystem server is scoped to the workspace and carries WRITE risk (gated).
6. **Verified-only memory.** Only execution/verification-passed results are
   remembered, so a hallucinated "success" cannot poison future runs.

## Known limitations (be honest)
- `run_shell` does **not** block network (legitimate commands like `pip`, `git`,
  `npm` need it). It is gated by approval; use `plan`/`gated` mode for untrusted
  tasks. `run_python` *does* block network by default.
- An allowlisted interpreter (`python -c …`) can run arbitrary code — but inside
  the sandbox, and `run_python`'s variant is network-isolated.
- Pure-Python network isolation and memory caps are **best-effort on Windows
  without Docker**. For stronger isolation, run execution in a throwaway Docker
  container (optional power-up).
- A timeout bounds runaway processes but not all resource abuse on Windows.

## Recommendations
- Keep **gated** mode for anything you don't fully trust; reserve `autonomous`
  for routine work in repos you own.
- Use the Docker-backed sandbox when available for hard isolation.
- Treat the workspace you open as the blast radius — open a project dir, not `/`.
