from __future__ import annotations

from typing import Any

from heddle.store import HeddleStore


def record_skipped_snapshot(
    store: HeddleStore,
    repo_id: str,
    commit_sha: str,
    reason: str,
) -> int:
    return store.create_edge_snapshot(
        repo_id=repo_id,
        commit_sha=commit_sha,
        source="loomweave",
        source_version=reason,
        completeness="SKIPPED",
    )


def _entity_id(row: dict[str, Any]) -> str | None:
    nested = row.get("entity")
    raw = row.get("id")
    if raw is None and isinstance(nested, dict):
        raw = nested.get("id")
    return raw if isinstance(raw, str) and raw else None


def edges_from_neighborhood(neighborhood: dict[str, Any]) -> set[tuple[str, str, str]]:
    entity = neighborhood.get("entity")
    center = _entity_id(entity if isinstance(entity, dict) else {})
    if center is None:
        raise ValueError("neighborhood missing entity.id")
    truncated = neighborhood.get("truncated")
    if isinstance(truncated, dict) and any(
        truncated.get(bucket) is True for bucket in ("callers", "callees")
    ):
        raise ValueError("truncated neighborhood cannot be snapshotted as complete")

    edges: set[tuple[str, str, str]] = set()
    for caller in _entity_rows(neighborhood, "callers"):
        caller_id = _entity_id(caller)
        if caller_id:
            edges.add((caller_id, center, "calls"))
    for callee in _entity_rows(neighborhood, "callees"):
        callee_id = _entity_id(callee)
        if callee_id:
            edges.add((center, callee_id, "calls"))
    for ref_in in _entity_rows(neighborhood, "references_in"):
        ref_id = _entity_id(ref_in)
        if ref_id:
            edges.add((ref_id, center, "references"))
    for ref_out in _entity_rows(neighborhood, "references_out"):
        ref_id = _entity_id(ref_out)
        if ref_id:
            edges.add((center, ref_id, "references"))
    return edges


def _entity_rows(neighborhood: dict[str, Any], key: str) -> list[dict[str, Any]]:
    rows = neighborhood.get(key)
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]
