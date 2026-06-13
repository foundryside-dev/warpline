from __future__ import annotations

from typing import Any

from heddle.siblings import WorkClient, priority_from_work, work_enrichment_for_sei

_SUGGESTED_VERIFICATION = [
    {"kind": "test", "command": "run tests touching this entity if known"},
    {"kind": "inspection", "command": "inspect callers and behavior at this boundary"},
]


def _empty_enrichment() -> dict[str, list[Any]]:
    # advisory facts only; absence is explicit emptiness, never an implied
    # clean/allowed state (DECONFLICTION-FIRST).
    return {"work": [], "risk": [], "governance": [], "requirements": []}


def render_reverify_worklist(
    *,
    changed: list[dict[str, Any]],
    affected: list[dict[str, Any]],
    completeness: str,
    staleness: dict[str, Any],
    work_client: WorkClient | None = None,
) -> tuple[list[dict[str, Any]], bool, list[dict[str, Any]]]:
    """Render the frozen reverify worklist items.

    Returns ``(items, work_seen, filigree_candidates)``. The changed entities are
    always present (reason ``changed``) so a solo/NO_SNAPSHOT worklist is still
    non-empty; downstream entities are added when a snapshot exists.
    """

    rows: list[tuple[dict[str, Any], str, int, list[Any]]] = []
    for entry in changed:
        rows.append((entry.get("entity", {}), "changed", 0, []))
    for entry in affected:
        rows.append(
            (
                entry.get("entity", {}),
                "downstream",
                entry.get("depth", 1),
                entry.get("via_edges", []),
            )
        )

    items: list[dict[str, Any]] = []
    work_seen = False
    candidates: list[dict[str, Any]] = []
    for entity, reason, depth, why in rows:
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
        items.append(
            {
                "entity": entity,
                "priority": priority,
                "reason": reason,
                "depth": depth,
                "why": why,
                "suggested_verification": _SUGGESTED_VERIFICATION,
                "enrichment": enrichment,
            }
        )
    return items, work_seen, candidates
