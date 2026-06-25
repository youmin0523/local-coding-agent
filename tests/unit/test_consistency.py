"""Self-consistency disagreement scoring + probe."""

from __future__ import annotations

from lca.routing.consistency import disagreement_score, probe_disagreement


def test_identical_samples_zero_disagreement():
    assert disagreement_score(["the answer is 42", "the answer is 42"]) == 0.0


def test_disjoint_samples_high_disagreement():
    assert disagreement_score(["alpha beta gamma", "delta epsilon zeta"]) == 1.0


def test_partial_overlap_is_between():
    score = disagreement_score(["the cat sat", "the cat ran"])
    assert 0.0 < score < 1.0


def test_single_or_empty_sample_is_zero():
    assert disagreement_score(["only one"]) == 0.0
    assert disagreement_score(["", ""]) == 0.0


async def test_probe_uses_k_samples():
    calls = {"n": 0}
    answers = ["foo bar", "baz qux"]

    async def sample_once() -> str:
        calls["n"] += 1
        return answers[calls["n"] % len(answers)]

    score = await probe_disagreement(sample_once, k=2)
    assert calls["n"] == 2
    assert score == 1.0  # the two distinct answers are disjoint
