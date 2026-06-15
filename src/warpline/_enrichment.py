"""Pure staleness/completeness enrichment helpers (internal API).

Extracted from ``commands.py`` (Rung 0). Dependency is strictly one-way:
``commands.py -> _enrichment``; this module imports nothing from warpline and is
structurally incapable of gating (enrich-only doctrine, verified by its import
list: only ``typing.Any``). No store, no git, no I/O.
"""

from __future__ import annotations

from typing import Any

# enrichment.edges value for each completeness level.
EDGES_FOR_COMPLETENESS = {
    "FULL": "present",
    "DELTA": "partial",
    "NO_SNAPSHOT": "absent",
    "SKIPPED": "skipped",
}


def is_stale(staleness: dict[str, Any]) -> bool:
    """The snapshot was captured at a commit behind HEAD.

    ``commits_behind`` is the live answer to ``snapshot_commit..HEAD``; any
    positive count means the stored edge graph no longer describes HEAD. A
    ``None`` count means we could not ask git (detached snapshot commit, shallow
    clone) — we treat that as *unknown, therefore not-proven-fresh* and surface
    it as stale rather than silently claiming completeness.
    """

    behind = staleness.get("commits_behind")
    if behind is None:
        return staleness.get("snapshot_commit") is not None
    return int(behind) > 0


def edges_enrichment(completeness: str, staleness: dict[str, Any]) -> str:
    """Map (completeness, staleness) → the closed ``enrichment.edges`` vocab.

    A FULL-or-DELTA snapshot that is *behind HEAD* downgrades to the live
    ``"stale"`` value: the edge graph is real but no longer describes the
    working tree, so completeness must NOT be claimed. Without this, a stale-
    but-FULL snapshot would emit ``edges:"present"`` and hand an agent a
    confident affected-set with zero freshness warning (PDR-0023: the quiet
    segfault). NO_SNAPSHOT / SKIPPED are already-honest "we have nothing" states
    and are reported as-is regardless of staleness.
    """

    base = EDGES_FOR_COMPLETENESS.get(completeness, "absent")
    if completeness in {"FULL", "DELTA"} and is_stale(staleness):
        return "stale"
    return base


def staleness_warnings(completeness: str, staleness: dict[str, Any]) -> list[str]:
    if completeness in {"FULL", "DELTA"} and is_stale(staleness):
        behind = staleness.get("commits_behind")
        commit = str(staleness.get("snapshot_commit") or "unknown")[:8]
        if behind is None:
            tail = "snapshot commit is not on HEAD's history; freshness unknown"
        else:
            tail = f"{behind} commit(s) behind HEAD"
        return [
            f"STALE: edge snapshot @ {commit} is {tail}; affected set is not complete for "
            "HEAD — recapture (warpline capture-snapshot) before trusting completeness"
        ]
    return []


def completeness_warnings(completeness: str) -> list[str]:
    return {
        "NO_SNAPSHOT": ["NO_SNAPSHOT: downstream traversal unavailable; changed set only"],
        "SKIPPED": ["SKIPPED: graph snapshot was skipped; changed set only"],
        "DELTA": ["DELTA: graph snapshot is partial; inspect failed_entities or staleness"],
    }.get(completeness, [])
