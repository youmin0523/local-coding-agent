---
name: summarize-logs
description: Summarize a log or error output and find the root cause, grounded strictly in the actual lines. Use when asked to summarize logs, triage a build/test/run output, analyze a stack-trace dump, or explain what went wrong in a log file.
license: MIT
metadata:
  version: "1.0"
  author: lca
---

# Summarize logs (grounded, no guessing)

The rule: **every claim must trace to a line that is actually in the log.** If the
log doesn't contain the cause, say so — do not invent one.

## Procedure

1. **Read the real log** (use the read/search tools). For large logs, search for
   `error`, `exception`, `traceback`, `fatal`, `failed`, `warn`, `panic`,
   non-zero exit codes, and the last lines before a crash.
2. **Separate root cause from cascade.** The *first* error in time is usually the
   cause; later errors are often consequences. For a stack trace, the bottom
   frame is where it was raised.
3. **Group repeats.** "Connection refused ×148" is one finding, not 148.
4. **Quote exact evidence** — file:line or a short verbatim snippet for each claim.
5. **State the fix** only if the log (or a reference doc) supports it; otherwise
   list what additional info is needed.

## Output shape

```
## Summary
<2-3 sentences: what happened, did it succeed/fail>

## Root cause
<the earliest/authoritative error> — evidence: `path:line` "exact text"

## Other findings
- <grouped warning/error> (×N) — evidence: ...

## Suggested fix
<concrete step, tied to evidence; or "insufficient info: need X">
```

## Validate

- Every bullet cites a line that exists in the input.
- Root cause is distinguished from downstream noise.
- No invented file names, error codes, or causes. If unsure, abstain.
