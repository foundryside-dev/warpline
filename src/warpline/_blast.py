"""Blast-pipeline prep helpers (internal API).

Extracted from ``commands.py`` (Rung 0). Dependency is strictly one-way:
``commands.py -> _blast``; this module never imports ``commands``.

Doctrine (no-mirror / SEI-orthogonality): reads the store passed in, calls git
rev-list, writes nothing, mints no identifier; operates on warpline-local
``entity_key_id`` integers and SEI strings supplied by the store. ``WarplineStore``
is always a parameter — never opened inside.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from warpline.errors import BadRevisionError
from warpline.refs import entity_view
from warpline.store import WarplineStore


def _as_int(value: object) -> int:
    # Strict-assert form (matching the original ``commands._as_int``), deliberately
    # distinct from ``propagation._as_int`` (permissive int|str). Not imported across
    # modules: each owner keeps the variant its call sites need.
    assert isinstance(value, int)
    return value


def rev_range_commits(repo: Path, rev_range: str | None) -> set[str] | None:
    if rev_range is None:
        return None
    try:
        proc = subprocess.run(
            ["git", "rev-list", rev_range],
            cwd=repo,
            check=True,
            text=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.strip() or exc.stdout.strip() or str(exc)
        raise BadRevisionError(f"invalid rev_range {rev_range!r}: {detail}") from exc
    return {line for line in proc.stdout.splitlines() if line}


def resolve_changed_inputs(
    store: WarplineStore,
    repo: Path,
    *,
    rev_range: str | None,
    changed_refs: list[dict[str, str]],
    changed_entity_key_ids: list[int],
) -> tuple[list[int], list[dict[str, Any]], list[dict[str, Any]]]:
    """Resolve the caller's change-set into stored entity keys.

    Returns ``(key_ids, resolved, unresolved)``. The miss-set is the honesty
    surface for the resolve join: a ``changed_ref`` that does not map to any
    stored entity_key — or a raw ``entity_key_id`` that is unknown to this repo's
    store — was, before this change, silently dropped, so an agent asking "does
    my change break anything?" got a confident affected-set computed over an
    *incomplete* seed set with no signal that half its refs never resolved.
    Every unresolved input now appears in ``unresolved`` with a machine-readable
    ``reason`` so the caller can ask "did my SEI actually resolve into the
    snapshot?" and get a yes/no, not a silent omission.
    """

    ids: set[int] = set()
    resolved: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []

    # Raw entity_key_ids are a compatibility seed, not a federation key; still,
    # an id unknown to this store is a miss the caller must see.
    known_ids = store.entity_keys_by_ids(repo, sorted(set(changed_entity_key_ids)))
    for key_id in changed_entity_key_ids:
        if key_id in known_ids:
            ids.add(key_id)
            row = known_ids[key_id]
            resolved.append(
                {
                    "ref": {"kind": "warpline_entity_key_id", "value": key_id},
                    "entity_key_id": key_id,
                    "sei": row.get("sei"),
                    "locator": row.get("locator"),
                }
            )
        else:
            unresolved.append(
                {
                    "ref": {"kind": "warpline_entity_key_id", "value": key_id},
                    "reason": "unknown_entity_key_id",
                }
            )

    for ref in changed_refs:
        resolved_row = store.resolve_ref(repo, ref["kind"], ref["value"])
        if resolved_row is not None:
            resolved_id = _as_int(resolved_row["id"])
            ids.add(resolved_id)
            resolved.append(
                {
                    "ref": ref,
                    "entity_key_id": resolved_id,
                    "sei": resolved_row.get("sei"),
                    "locator": resolved_row.get("locator"),
                }
            )
        else:
            reason = "sei_not_in_snapshot" if ref.get("kind") == "sei" else "ref_not_in_snapshot"
            unresolved.append({"ref": ref, "reason": reason})

    if rev_range is not None:
        commit_shas = rev_range_commits(repo, rev_range)
        for event in store.list_change_events(repo, commit_shas=commit_shas):
            event_key_id = event.get("entity_key_id")
            if isinstance(event_key_id, int):
                ids.add(event_key_id)

    return sorted(ids), resolved, unresolved


def enrich_blast(
    store: WarplineStore, repo: Path, result: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    ids: set[int] = set()
    for row in result.get("changed", []):
        if isinstance(row.get("entity_key_id"), int):
            ids.add(row["entity_key_id"])
    for row in result.get("affected", []):
        if isinstance(row.get("entity_key_id"), int):
            ids.add(row["entity_key_id"])
        for edge in row.get("via_edges", []):
            for end in ("from", "to"):
                if isinstance(edge.get(end), int):
                    ids.add(edge[end])
    key_rows = store.entity_keys_by_ids(repo, sorted(ids))

    def view(key_id: Any) -> dict[str, Any]:
        return entity_view(key_rows.get(int(key_id)) if isinstance(key_id, int) else None)

    changed = [{"entity": view(row.get("entity_key_id"))} for row in result.get("changed", [])]
    affected = []
    for row in result.get("affected", []):
        via = [
            {
                "from": str(edge.get("from")),
                "to": str(edge.get("to")),
                "kind": edge.get("kind"),
                "confidence": edge.get("confidence"),
            }
            for edge in row.get("via_edges", [])
        ]
        affected.append(
            {"entity": view(row.get("entity_key_id")), "depth": row.get("depth"), "via_edges": via}
        )
    return changed, affected
