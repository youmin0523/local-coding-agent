---
name: debug-from-traceback
description: Diagnose and fix a Python or JavaScript error from its traceback or failing-test output, then verify the fix by running checks. Use when given an exception, stack trace, failing pytest/vitest output, or an error message and asked to fix it.
license: MIT
metadata:
  version: "1.0"
  author: lca
---

# Debug from a traceback

Let execution be the judge: hypothesize, fix the smallest thing, then re-run.

## Procedure

1. **Read the traceback to its real origin.** Python: the **bottom** frame is
   where the exception was raised; read the exception type + message there. JS:
   the top stack frame in app code (skip node_modules).
2. **Locate the line** in the repo (search/read tools). Read the surrounding
   code and the values involved — don't guess at the cause.
3. **Match known patterns.** Consult `reference_docs` for the error class, e.g.
   SQLAlchemy `MissingGreenlet`/`DetachedInstanceError`, asyncio loop errors,
   Pydantic v1→v2 breaks, React "Rendered more hooks…", CORS, `undefined` reads.
   These have standard fixes — apply the matching one.
4. **Form one hypothesis** and make the **minimal** change that addresses the
   root cause (not a symptom; not a broad rewrite).
5. **Reproduce + verify with the execution oracle.** Run `run_checks` (pytest /
   mypy / ruff) or the specific failing test. The error must disappear AND no new
   failure may appear. If it still fails, revise the hypothesis — repeat.
6. **Guard the fix** with a regression test that fails before and passes after,
   when practical.

## Anti-patterns

- Catching/swallowing the exception to make it "pass" — fix the cause.
- Editing many files on a hunch before reproducing.
- Declaring it fixed without re-running the checks.

## Validate

- The original error no longer occurs when checks run.
- No new test/type/lint failures were introduced.
- The change is minimal and explained (what was wrong, why this fixes it).
