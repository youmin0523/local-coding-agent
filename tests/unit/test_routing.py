"""Difficulty estimation and the compute router."""

from __future__ import annotations

from lca.routing.difficulty import Difficulty, estimate_difficulty
from lca.routing.router import Router


def test_easy_task_is_easy():
    assert estimate_difficulty("rename this variable") == Difficulty.EASY
    assert estimate_difficulty("what is 2 + 2?") == Difficulty.EASY


def test_hard_task_is_hard():
    d = estimate_difficulty("refactor the architecture to fix a concurrency race condition")
    assert d == Difficulty.HARD


def test_file_count_and_disagreement_raise_difficulty():
    base = estimate_difficulty("update the handler")
    harder = estimate_difficulty("update the handler", file_count=3, disagreement=0.9)
    assert harder == Difficulty.HARD
    assert base != Difficulty.HARD


def test_router_easy_uses_fast_no_verify():
    plan = Router().plan("fix a typo")
    assert plan.model == "fast" and plan.samples == 1 and plan.verify is False


def test_router_hard_uses_brain_best_of_n_verified():
    plan = Router().plan("debug the deadlock in the distributed scheduler")
    assert plan.model == "brain" and plan.samples >= 3 and plan.verify is True


def test_router_falls_back_to_fast_without_brain():
    plan = Router(brain_available=False).plan("redesign the architecture")
    assert plan.model == "fast" and plan.verify is True
