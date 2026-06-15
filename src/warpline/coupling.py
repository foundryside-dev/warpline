"""Temporal co-change coupling derivation (Rung 2 Track A).

Pure derivation helpers for the co-change graph. Two entities are "coupled" when
they keep changing together in the same commit; the count of such co-changes is a
co-occurrence fact warpline OWNS, derived entirely from its own ``change_events``.

Doctrine:
- SEI-orthogonality / no-mirror — these helpers operate only on warpline-local
  ``entity_key_id`` integers and the counts warpline derives from them. They mint
  no identifier, parse no SEI, and read no sibling state. The SEI is joined at
  read time in the store, never here.
- Honesty invariant — below the sample floor, ``coupling_rate`` returns ``None``
  (the rate is not yet meaningful) and ``classify_confidence`` returns ``low``;
  a sparse pair is never dressed up as a high-confidence signal.

This module is a pure leaf: it imports nothing from ``warpline.commands`` or
``warpline.store`` (the store imports IT), so there is no import cycle.
"""

from __future__ import annotations

# Sample-size floor below which a coupling rate is not yet meaningful. Mirrors
# the confidence threshold so the two honesty signals agree.
_RATE_SAMPLE_FLOOR = 5

# Confidence thresholds on raw co-change count.
_CONFIDENCE_MEDIUM_FLOOR = 5
_CONFIDENCE_HIGH_FLOOR = 20


def derive_pairs_from_commit(entity_key_ids: list[int]) -> list[tuple[int, int]]:
    """All unordered pairs of a commit's changed entities, canonically ``a < b``.

    Duplicate ids collapse (a commit touches a given entity once for coupling
    purposes); the output is deterministic (sorted) so a rebuild reproduces the
    same set. An empty/singleton input yields no pairs.
    """

    ids = sorted(set(entity_key_ids))
    pairs: list[tuple[int, int]] = []
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            pairs.append((ids[i], ids[j]))
    return pairs


def classify_confidence(co_change_count: int) -> str:
    """Map a raw co-change count to a closed confidence vocab.

    ``< 5`` → ``low`` · ``5–19`` → ``medium`` · ``>= 20`` → ``high``.
    """

    if co_change_count >= _CONFIDENCE_HIGH_FLOOR:
        return "high"
    if co_change_count >= _CONFIDENCE_MEDIUM_FLOOR:
        return "medium"
    return "low"


def coupling_rate(co_change_count: int, total: int) -> float | None:
    """Fraction of an entity's changes that co-occurred with the partner.

    Returns ``None`` (suppressed) when the denominator is below the sample floor
    — the rate would over-read a handful of co-changes as a strong coupling. The
    rate is clamped to ``[0.0, 1.0]`` (co-change count can never exceed an
    entity's own total change count in a consistent store, but a rebuild race or
    divergent data must never emit a >1 rate).
    """

    if total < _RATE_SAMPLE_FLOOR or total <= 0:
        return None
    rate = co_change_count / total
    if rate < 0.0:
        return 0.0
    if rate > 1.0:
        return 1.0
    return rate
