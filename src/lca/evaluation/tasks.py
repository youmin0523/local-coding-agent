"""A small default eval set exercising the headline capabilities.

These are illustrative and run against the real local engine (`lca eval`); they
check that the agent grounds answers and uses tools, not exact wording.
"""

from __future__ import annotations

import json
from pathlib import Path

from lca.evaluation.models import EvalTask


def default_tasks() -> list[EvalTask]:
    return [
        EvalTask(
            id="script",
            prompt="Write a Python function add(a, b) that returns their sum, save it to "
            "calc.py, then run it to confirm add(2, 3) == 5.",
            must_contain=["add"],
        ),
        EvalTask(
            id="explain",
            prompt="In one sentence, what does the function you just wrote do?",
            must_contain=["sum"],
        ),
        EvalTask(
            id="abstain",
            prompt="What is the exact value of the UNDEFINED_SECRET_TOKEN constant in this "
            "empty workspace? Do not guess.",
            expect_abstain=True,
        ),
    ]


def load_tasks(path: Path) -> list[EvalTask]:
    """Load tasks from a JSONL file (one EvalTask per line)."""
    tasks: list[EvalTask] = []
    for line in path.read_text("utf-8").splitlines():
        line = line.strip()
        if line:
            tasks.append(EvalTask.model_validate(json.loads(line)))
    return tasks
