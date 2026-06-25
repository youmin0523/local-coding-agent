"""The self-improvement loop — rejection-sampling fine-tuning (RLVR / STaR), local.

This is the concrete "learn like RL/DL" pipeline:

  rollout   — run the agent on tasks (best-of-N candidates)
  reward    — execution / verification is the verifiable reward (pass = 1)
  filter    — only verified-pass trajectories are kept (the memory write gate)
  dataset   — those verified experiences become the SFT corpus
  gradient  — QLoRA fine-tunes the 7B on that corpus (WSL2; training/train_qlora.py)

The first four steps run fully on-device here; the gradient step is the optional
WSL2 stage. The no-train experience memory is the in-context half of the same loop.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from pydantic import BaseModel

from lca.core.agent import Agent
from lca.core.session import Session
from lca.evaluation.models import EvalTask
from lca.memory.store import MemoryStore

AgentFactory = Callable[[], Agent]


class LearnReport(BaseModel):
    rollouts: int
    rewarded: int  # verified-pass trajectories (reward = 1)
    learned_total: int  # experiences in memory afterwards
    dataset_path: str
    dataset_examples: int

    @property
    def reward_rate(self) -> float:
        return self.rewarded / self.rollouts if self.rollouts else 0.0


async def run_rollouts(factory: AgentFactory, tasks: list[EvalTask], workspace: Path) -> int:
    """Run each task through the agent; return the count that earned reward (pass)."""
    rewarded = 0
    for task in tasks:
        agent = factory()
        session = Session(workspace_root=workspace)
        passed = False
        async for event in agent.run_turn(session, task.prompt):
            if event.type == "verification" and event.verdict == "pass":
                passed = True
        rewarded += int(passed)
    return rewarded


def export_sft(store: MemoryStore, out: Path) -> int:
    """Write verified episodic experiences as an SFT dataset (JSONL). Returns count."""
    items = store.dump(kind="episodic")
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        for item in items:
            fh.write(json.dumps({"prompt": item.title, "response": item.content}) + "\n")
    return len(items)
