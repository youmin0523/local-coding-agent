"""The permission policy matrix across autonomy modes."""

from __future__ import annotations

from lca.core.messages import ToolCall
from lca.permissions.modes import AutonomyMode
from lca.permissions.policy import Decision, DefaultPolicy
from lca.tools.base import RiskLevel


def _call(name: str = "t") -> ToolCall:
    return ToolCall(id="1", name=name, arguments={})


def test_read_always_allowed():
    p = DefaultPolicy()
    for mode in AutonomyMode:
        assert p.evaluate(_call(), RiskLevel.READ, mode) == Decision.ALLOW


def test_gated_asks_for_write_and_shell():
    p = DefaultPolicy()
    assert p.evaluate(_call(), RiskLevel.WRITE, AutonomyMode.GATED) == Decision.ASK
    assert p.evaluate(_call(), RiskLevel.SHELL, AutonomyMode.GATED) == Decision.ASK
    assert p.evaluate(_call(), RiskLevel.NETWORK, AutonomyMode.GATED) == Decision.ASK


def test_plan_denies_side_effects():
    p = DefaultPolicy()
    assert p.evaluate(_call(), RiskLevel.WRITE, AutonomyMode.PLAN) == Decision.DENY
    assert p.evaluate(_call(), RiskLevel.SHELL, AutonomyMode.PLAN) == Decision.DENY


def test_autonomous_respects_ceiling():
    p = DefaultPolicy(autonomous_ceiling=RiskLevel.SHELL)
    assert p.evaluate(_call(), RiskLevel.WRITE, AutonomyMode.AUTONOMOUS) == Decision.ALLOW
    assert p.evaluate(_call(), RiskLevel.SHELL, AutonomyMode.AUTONOMOUS) == Decision.ALLOW
    # NETWORK is above the SHELL ceiling, so it still asks.
    assert p.evaluate(_call(), RiskLevel.NETWORK, AutonomyMode.AUTONOMOUS) == Decision.ASK


def test_autonomous_with_network_ceiling_allows_network():
    p = DefaultPolicy(autonomous_ceiling=RiskLevel.NETWORK)
    assert p.evaluate(_call(), RiskLevel.NETWORK, AutonomyMode.AUTONOMOUS) == Decision.ALLOW


def test_allow_cache_short_circuits():
    p = DefaultPolicy()
    cache = {"write_file"}
    assert (
        p.evaluate(_call("write_file"), RiskLevel.WRITE, AutonomyMode.GATED, cache)
        == Decision.ALLOW
    )
