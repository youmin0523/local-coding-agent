"""Best-of-N consensus selection.

For checkable tasks the agent can sample N candidates and keep the one the group
agrees on — clustering by a *behavioral* signature (e.g. test output) rather than
text, since two correct answers can look different. Returns the representative of
the largest cluster plus the agreement ratio, which feeds confidence/abstention.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable


def select_by_consensus[T](candidates: list[T], key: Callable[[T], str]) -> tuple[T, float]:
    """Return (representative_of_largest_cluster, agreement_ratio).

    ``key`` maps a candidate to a signature; candidates with equal signatures are
    considered equivalent. Raises ValueError on an empty input.
    """
    if not candidates:
        raise ValueError("no candidates to select from")
    clusters: dict[str, list[T]] = defaultdict(list)
    for cand in candidates:
        clusters[key(cand)].append(cand)
    largest = max(clusters.values(), key=len)
    return largest[0], len(largest) / len(candidates)
