"""Difficulty routing and test-time compute allocation."""

from lca.routing.difficulty import Difficulty, estimate_difficulty
from lca.routing.router import RoutePlan, Router

__all__ = ["Difficulty", "RoutePlan", "Router", "estimate_difficulty"]
