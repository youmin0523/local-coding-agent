"""Evaluation harness: run tasks through the agent and score them."""

from lca.evaluation.harness import run_eval
from lca.evaluation.models import EvalTask, Scorecard, TaskResult
from lca.evaluation.tasks import default_tasks, load_tasks

__all__ = [
    "EvalTask",
    "Scorecard",
    "TaskResult",
    "default_tasks",
    "load_tasks",
    "run_eval",
]
