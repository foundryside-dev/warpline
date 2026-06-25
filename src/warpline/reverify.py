from __future__ import annotations

from collections.abc import Callable
from typing import Any

from warpline.listing import reason
from warpline.siblings import WorkClient, priority_from_work, work_enrichment_for_sei

_SUGGESTED_VERIFICATION = [
    {"kind": "test", "command": "run tests touching this entity if known"},
    {"kind": "inspection", "command": "inspect callers and behavior at this boundary"},
]


def _empty_enrichment() -> dict[str, list[Any]]:
    # advisory facts only; absence is explicit emptiness, never an implied
    # clean/allowed state (DECONFLICTION-FIRST).
    return {"work": [], "risk": [], "governance": [], "requirements": []}


def _default_verification() -> dict[str, Any]:
    """Honest default when no verification source is wired (advisory)."""

    return {
        "state": "unverified",
        "last_verified_at": None,
        "last_verified_commit": None,
        "decay": {"commits_behind": None},
        "reason": reason(
            "disabled",
            cause="no local verification source is configured for this worklist",
            fix=(
                "record a gate pass with `warpline verify-record --commit <sha> "
                "--kind test_pass`"
            ),
        ),
    }


def render_reverify_worklist(
    *,
    changed: list[dict[str, Any]],
    affected: list[dict[str, Any]],
    completeness: str,
    staleness: dict[str, Any],
    work_client: WorkClient | None = None,
    changed_key_ids: list[int | None] | None = None,
    affected_key_ids: list[int | None] | None = None,
    verification_for: Callable[[int | None], dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], bool, list[dict[str, Any]]]:
    """Render the frozen reverify worklist items.

    Returns ``(items, work_seen, filigree_candidates)``. The changed entities are
    always present (reason ``changed``) so a solo/NO_SNAPSHOT worklist is still
    non-empty; downstream entities are added when a snapshot exists.

    ``verification_for`` (advisory, Rung 2 Track B) maps an ``entity_key_id`` to
    its verification-freshness block; ``changed_key_ids`` / ``affected_key_ids``
    are aligned 1:1 with ``changed`` / ``affected`` so the block can be attached
    without threading the internal key id into the FROZEN ``{locator, sei}``
    entity view. When ``verification_for`` is None the block defaults to an
    honest ``unverified`` (no source configured).
    """

    ckids = changed_key_ids or [None] * len(changed)
    akids = affected_key_ids or [None] * len(affected)
    rows: list[tuple[dict[str, Any], str, int, list[Any], int | None]] = []
    for entry, kid in zip(changed, ckids, strict=True):
        rows.append((entry.get("entity", {}), "changed", 0, [], kid))
    for entry, kid in zip(affected, akids, strict=True):
        rows.append(
            (
                entry.get("entity", {}),
                "downstream",
                entry.get("depth", 1),
                entry.get("via_edges", []),
                kid,
            )
        )

    items: list[dict[str, Any]] = []
    work_seen = False
    candidates: list[dict[str, Any]] = []
    for entity, reason_str, depth, why, kid in rows:
        enrichment = _empty_enrichment()
        priority = "unknown"
        sei = entity.get("sei")
        if work_client is not None and isinstance(sei, str) and sei:
            work_items = work_enrichment_for_sei(work_client, sei)
            if work_items:
                work_seen = True
                enrichment["work"] = work_items
                priority = priority_from_work(work_items)
                for work_item in work_items:
                    candidates.append(
                        {
                            "proposed_action": "review_linked_issue",
                            "issue_id": work_item.get("issue_id"),
                            "entity": entity,
                        }
                    )
        verification = (
            verification_for(kid) if verification_for is not None else _default_verification()
        )
        items.append(
            {
                "entity": entity,
                "priority": priority,
                "reason": reason_str,
                "depth": depth,
                "why": why,
                "suggested_verification": _SUGGESTED_VERIFICATION,
                "enrichment": enrichment,
                "verification": verification,
            }
        )
    return items, work_seen, candidates
