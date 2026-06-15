from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

from warpline.envelope import build_envelope, enrichment_state
from warpline.errors import BadRevisionError, InvalidChangedRefsError
from warpline.federation import LegisClient, RiskClient, consult_federation
from warpline.listing import (
    apply_filters,
    apply_group_by,
    apply_overflow,
    apply_page,
    apply_sort,
)
from warpline.loomweave import LoomweaveMcpClient, LoomweaveProbe
from warpline.propagation import blast_radius as compute_blast_radius
from warpline.refs import (
    changed_ref_for_row,
    entity_view,
    parse_changed_refs,
    parse_entity_ref,
)
from warpline.reverify import render_reverify_worklist
from warpline.siblings import RenameFeed, WorkClient
from warpline.snapshot import capture_edge_snapshot
from warpline.store import WarplineStore, default_store_path

# FROZEN schema URIs (one contract per tool; endorsed name and shim share it).
SCHEMA_CHANGE_LIST = "warpline.change_list.v1"
SCHEMA_ENTITY_TIMELINE = "warpline.entity_timeline.v1"
SCHEMA_ENTITY_CHURN_COUNT = "warpline.entity_churn_count.v1"
SCHEMA_IMPACT_RADIUS = "warpline.impact_radius.v1"
SCHEMA_REVERIFY_WORKLIST = "warpline.reverify_worklist.v1"
SCHEMA_EDGE_SNAPSHOT = "warpline.edge_snapshot.v1"

# enrichment.edges value for each completeness level.
_EDGES_FOR_COMPLETENESS = {
    "FULL": "present",
    "DELTA": "partial",
    "NO_SNAPSHOT": "absent",
    "SKIPPED": "skipped",
}


def _is_stale(staleness: dict[str, Any]) -> bool:
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
    return _as_int(behind) > 0


def _edges_enrichment(completeness: str, staleness: dict[str, Any]) -> str:
    """Map (completeness, staleness) → the closed ``enrichment.edges`` vocab.

    A FULL-or-DELTA snapshot that is *behind HEAD* downgrades to the live
    ``"stale"`` value: the edge graph is real but no longer describes the
    working tree, so completeness must NOT be claimed. Without this, a stale-
    but-FULL snapshot would emit ``edges:"present"`` and hand an agent a
    confident affected-set with zero freshness warning (PDR-0023: the quiet
    segfault). NO_SNAPSHOT / SKIPPED are already-honest "we have nothing" states
    and are reported as-is regardless of staleness.
    """

    base = _EDGES_FOR_COMPLETENESS.get(completeness, "absent")
    if completeness in {"FULL", "DELTA"} and _is_stale(staleness):
        return "stale"
    return base


def _staleness_warnings(completeness: str, staleness: dict[str, Any]) -> list[str]:
    if completeness in {"FULL", "DELTA"} and _is_stale(staleness):
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


def session_context(repo: Path) -> str:
    """A one-line temporal snapshot for the SessionStart hook (fail-soft)."""

    try:
        with WarplineStore.open(default_store_path(repo)) as store:
            events = store.list_change_events(repo)
            snapshot = store.latest_snapshot(repo)
    except Exception:
        return "warpline: temporal store unavailable"
    if not events:
        return "warpline: 0 change events tracked (run `warpline backfill`)"
    if snapshot is None or snapshot.get("completeness") == "SKIPPED":
        snap = "no edge snapshot (impact/reverify return NO_SNAPSHOT until capture)"
    else:
        snap = f"snapshot {snapshot.get('completeness')} @ {str(snapshot.get('commit_sha'))[:8]}"
    return f"warpline: {len(events)} change events tracked; {snap}"


def _rev_range_commits(repo: Path, rev_range: str | None) -> set[str] | None:
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


def _page(limit: int) -> dict[str, Any]:
    return {"limit": limit, "next_cursor": None, "has_more": False}


def _filters_echo(filters: Any) -> dict[str, Any]:
    """Echo the caller's active filters into the query block (empty when none),
    so the response is self-describing about what scoping was applied."""

    if not isinstance(filters, dict):
        return {}
    return {k: v for k, v in filters.items() if v is not None}


def _as_int(value: object) -> int:
    assert isinstance(value, int)
    return value


def _resolve_changed_inputs(
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
        commit_shas = _rev_range_commits(repo, rev_range)
        for event in store.list_change_events(repo, commit_shas=commit_shas):
            event_key_id = event.get("entity_key_id")
            if isinstance(event_key_id, int):
                ids.add(event_key_id)

    return sorted(ids), resolved, unresolved


def _unresolved_warnings(unresolved: list[dict[str, Any]]) -> list[str]:
    if not unresolved:
        return []
    refs = ", ".join(str(item["ref"].get("value")) for item in unresolved)
    return [
        f"UNRESOLVED: {len(unresolved)} changed ref(s) did not resolve into the store and were "
        f"NOT seeded into the affected-set traversal ({refs}); see data.unresolved"
    ]


# ---------------------------------------------------------------------------
# warpline_change_list — warpline.change_list.v1
# ---------------------------------------------------------------------------
def _rev_range_from_refs(
    rev_range: str | None, base_ref: str | None, head_ref: str | None
) -> str | None:
    """Resolve the effective rev range. ``base_ref``/``head_ref`` are an explicit
    two-ended alternative to ``rev_range`` (``base..head``); supplying both forms
    is a conflict the caller must resolve, not a silently-dropped knob."""

    if base_ref is None and head_ref is None:
        return rev_range
    if rev_range is not None:
        raise BadRevisionError(
            "pass either rev_range OR base_ref/head_ref, not both",
            rejected_field="rev_range",
        )
    base = base_ref if base_ref is not None else "HEAD"
    head = head_ref if head_ref is not None else "HEAD"
    return f"{base}..{head}"


def change_list(
    repo: Path,
    rev_range: str | None = None,
    *,
    base_ref: str | None = None,
    head_ref: str | None = None,
    filters: Any = None,
    sort_by: str | None = None,
    sort_order: str | None = None,
    cursor: Any = None,
    include_next_actions: bool = True,
    limit: int = 50,
) -> dict[str, Any]:
    effective_range = _rev_range_from_refs(rev_range, base_ref, head_ref)
    commit_shas = _rev_range_commits(repo, effective_range)
    with WarplineStore.open(default_store_path(repo)) as store:
        events = store.list_change_events(repo, commit_shas=commit_shas)
        items: list[dict[str, Any]] = []
        changed_refs: list[dict[str, str]] = []
        seen_refs: set[tuple[str, str]] = set()
        key_ids: list[int] = []
        has_sei = False
        for event in events:
            path = str(event.get("path"))
            view = entity_view(event, include_key_id=True, path=path)
            if view["sei"]:
                has_sei = True
            items.append(
                {
                    "change_id": f"warpline:change:{event.get('change_event_id')}",
                    "entity": view,
                    "change_kind": event.get("change_kind"),
                    "actor": event.get("actor"),
                    "commit": event.get("commit_sha"),
                    "changed_at": event.get("changed_at"),
                }
            )
            ref = changed_ref_for_row(event)
            ref_key = (ref["kind"], ref["value"])
            if ref_key not in seen_refs:
                seen_refs.add(ref_key)
                changed_refs.append(ref)
            key_id = event.get("entity_key_id")
            if isinstance(key_id, int) and key_id not in key_ids:
                key_ids.append(key_id)

        # Filter → sort → overflow-bound → page: the list-ergonomics pipeline,
        # each step honoring its advertised knob or rejecting it loudly.
        items = apply_filters(items, tool="warpline_change_list", filters=filters)
        items = apply_sort(
            items, tool="warpline_change_list", sort_by=sort_by, sort_order=sort_order
        )
        items, overflow_warnings, overflow = apply_overflow(
            items, repo=repo, tool="warpline_change_list", schema=SCHEMA_CHANGE_LIST
        )
        items, page = apply_page(items, limit=limit, cursor=cursor)

        data = {
            "items": items,
            "changed_refs": changed_refs,
            "overflow": overflow,
            "page": page,
        }
        next_actions: dict[str, Any] = {}
        if include_next_actions:
            next_actions = {
                "warpline_reverify_worklist_get": {
                    "tool": "warpline_reverify_worklist_get",
                    "arguments": {
                        "repo": str(repo),
                        "changed_entity_key_ids": key_ids,
                        "changed_refs": changed_refs,
                        "depth": 2,
                    },
                },
                "warpline_impact_radius_get": {
                    "tool": "warpline_impact_radius_get",
                    "arguments": {
                        "repo": str(repo),
                        "changed_entity_key_ids": key_ids,
                        "changed_refs": changed_refs,
                        "depth": 2,
                    },
                },
            }
        query = {
            "repo": str(repo),
            "tool": "warpline_change_list",
            "arguments": {"rev_range": effective_range},
            "filters": _filters_echo(filters),
            "sort": {"by": sort_by or "changed_at", "order": sort_order or "asc"},
            "page": {"limit": limit, "cursor": cursor},
        }
        return build_envelope(
            SCHEMA_CHANGE_LIST,
            query=query,
            data=data,
            enrichment=enrichment_state(sei="present" if has_sei else "absent"),
            next_actions=next_actions,
            warnings=overflow_warnings,
        )


# ---------------------------------------------------------------------------
# warpline_entity_timeline_get — warpline.entity_timeline.v1
# ---------------------------------------------------------------------------
def entity_timeline(
    repo: Path,
    entity: Any,
    *,
    filters: Any = None,
    sort_by: str | None = None,
    sort_order: str | None = None,
    cursor: Any = None,
    limit: int = 50,
    rename_feed: RenameFeed | None = None,
) -> dict[str, Any]:
    ref = parse_entity_ref(entity)
    value = ref["value"]
    with WarplineStore.open(default_store_path(repo)) as store:
        aliases = rename_feed.aliases(value) if rename_feed is not None else [value]
        rows: list[dict[str, Any]] = []
        seen_events: set[Any] = set()
        for alias in aliases:
            for row in store.timeline(repo, alias):
                marker = row.get("change_event_id")
                if marker in seen_events:
                    continue
                seen_events.add(marker)
                rows.append(row)
        rows.sort(key=lambda r: (str(r.get("changed_at")), r.get("change_event_id") or 0))

        resolved = store.resolve_ref(repo, ref["kind"], value)
        if resolved is not None:
            locator = resolved.get("locator")
            sei = resolved.get("sei")
            sei_resolution = "resolved" if (isinstance(sei, str) and sei) else "unresolved"
        elif rows:
            locator = rows[0].get("locator")
            sei = rows[0].get("sei")
            sei_resolution = "resolved" if (isinstance(sei, str) and sei) else "unresolved"
        else:
            locator = value
            sei = None
            sei_resolution = "unknown"

        entity_out = {
            "locator": locator,
            "sei": sei if isinstance(sei, str) and sei else None,
            "sei_resolution": sei_resolution,
        }
        items = [
            {
                "change_kind": row.get("change_kind"),
                "actor": row.get("actor"),
                "commit": row.get("commit_sha"),
                "changed_at": row.get("changed_at"),
                "path": row.get("path"),
            }
            for row in rows
        ]
        items = apply_filters(items, tool="warpline_entity_timeline_get", filters=filters)
        items = apply_sort(
            items, tool="warpline_entity_timeline_get", sort_by=sort_by, sort_order=sort_order
        )
        items, overflow_warnings, overflow = apply_overflow(
            items, repo=repo, tool="warpline_entity_timeline_get", schema=SCHEMA_ENTITY_TIMELINE
        )
        items, page = apply_page(items, limit=limit, cursor=cursor)
        data = {"entity": entity_out, "items": items, "overflow": overflow, "page": page}
        query = {
            "repo": str(repo),
            "tool": "warpline_entity_timeline_get",
            "arguments": {"entity_ref": ref},
            "filters": _filters_echo(filters),
            "sort": {"by": sort_by or "changed_at", "order": sort_order or "asc"},
            "page": {"limit": limit, "cursor": cursor},
        }
        return build_envelope(
            SCHEMA_ENTITY_TIMELINE,
            query=query,
            data=data,
            enrichment=enrichment_state(
                sei="present" if entity_out["sei"] else "absent",
                governance="present" if rename_feed is not None else "unavailable",
            ),
            warnings=overflow_warnings,
        )


# ---------------------------------------------------------------------------
# warpline_entity_churn_count_get — warpline.entity_churn_count.v1 (NEW)
# ---------------------------------------------------------------------------
def entity_churn_count(
    repo: Path,
    entity_refs: Any,
    *,
    window: dict[str, Any] | None = None,
    sort_by: str = "churn_count",
    sort_order: str = "desc",
    cursor: Any = None,
    limit: int = 100,
) -> dict[str, Any]:
    refs = parse_changed_refs(entity_refs)
    window = window or {}
    since = window.get("since")
    until = window.get("until")
    rev_range = window.get("rev_range")
    with WarplineStore.open(default_store_path(repo)) as store:
        commit_shas = _rev_range_commits(repo, rev_range) if rev_range else None
        items: list[dict[str, Any]] = []
        has_sei = False
        for ref in refs:
            row = store.resolve_ref(repo, ref["kind"], ref["value"])
            if row is not None:
                agg = store.churn_for_entity(
                    repo, _as_int(row["id"]), commit_shas=commit_shas, since=since, until=until
                )
                ent = {"sei": row.get("sei"), "locator": row.get("locator")}
            else:
                agg = {"churn_count": 0, "first": None, "last": None, "last_actor": None}
                ent = {
                    "sei": ref["value"] if ref["kind"] == "sei" else None,
                    "locator": ref["value"] if ref["kind"] in {"locator", "qualname"} else None,
                }
            if ent["sei"]:
                has_sei = True
            items.append(
                {
                    "entity": ent,
                    "churn_count": agg["churn_count"],
                    "first_changed_at": agg["first"],
                    "last_changed_at": agg["last"],
                    "last_actor": agg["last_actor"],
                }
            )
        reverse = sort_order != "asc"
        if sort_by == "sei":
            items.sort(key=lambda i: str(i["entity"].get("sei") or ""), reverse=reverse)
        else:
            items.sort(key=lambda i: int(i["churn_count"]), reverse=reverse)
        window_out = {"since": since, "until": until, "rev_range": rev_range}
        items, overflow_warnings, overflow = apply_overflow(
            items,
            repo=repo,
            tool="warpline_entity_churn_count_get",
            schema=SCHEMA_ENTITY_CHURN_COUNT,
        )
        items, page = apply_page(items, limit=limit, cursor=cursor)
        data = {
            "items": items,
            "window": window_out,
            "overflow": overflow,
            "page": page,
        }
        query = {
            "repo": str(repo),
            "tool": "warpline_entity_churn_count_get",
            "arguments": {"entity_refs": refs, "window": window_out},
            "filters": {},
            "sort": {"by": sort_by, "order": sort_order},
            "page": {"limit": limit, "cursor": cursor},
        }
        return build_envelope(
            SCHEMA_ENTITY_CHURN_COUNT,
            query=query,
            data=data,
            enrichment=enrichment_state(sei="present" if has_sei else "absent"),
            warnings=overflow_warnings,
        )


def _enrich_blast(
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


# ---------------------------------------------------------------------------
# warpline_impact_radius_get — warpline.impact_radius.v1
# ---------------------------------------------------------------------------
def impact_radius(
    repo: Path,
    changed_entity_key_ids: list[int] | None = None,
    depth: int = 2,
    *,
    rev_range: str | None = None,
    changed_refs: Any = None,
    filters: Any = None,
    sort_by: str | None = None,
    sort_order: str | None = None,
    cursor: Any = None,
    limit: int = 100,
) -> dict[str, Any]:
    refs = parse_changed_refs(changed_refs)
    with WarplineStore.open(default_store_path(repo)) as store:
        key_ids, resolved, unresolved = _resolve_changed_inputs(
            store,
            repo,
            rev_range=rev_range,
            changed_refs=refs,
            changed_entity_key_ids=changed_entity_key_ids or [],
        )
        result = compute_blast_radius(store, repo, key_ids, depth)
        changed, affected = _enrich_blast(store, repo, result)
        completeness = result["completeness"]
        staleness = result["staleness"]
        # The affected set is the list surface (changed is the seed, kept whole).
        affected = apply_filters(affected, tool="warpline_impact_radius_get", filters=filters)
        affected = apply_sort(
            affected, tool="warpline_impact_radius_get", sort_by=sort_by, sort_order=sort_order
        )
        affected, overflow_warnings, overflow = apply_overflow(
            affected, repo=repo, tool="warpline_impact_radius_get", schema=SCHEMA_IMPACT_RADIUS
        )
        affected, page = apply_page(affected, limit=limit, cursor=cursor)
        data = {
            "completeness": completeness,
            "staleness": staleness,
            "resolved": resolved,
            "unresolved": unresolved,
            "changed": changed,
            "affected": affected,
            "overflow": overflow,
            "page": page,
        }
        query = {
            "repo": str(repo),
            "tool": "warpline_impact_radius_get",
            "arguments": {
                "rev_range": rev_range,
                "changed_entity_key_ids": key_ids,
                "depth": depth,
            },
            "filters": _filters_echo(filters),
            "sort": {"by": sort_by or "depth", "order": sort_order or "asc"},
            "page": {"limit": limit, "cursor": cursor},
        }
        return build_envelope(
            SCHEMA_IMPACT_RADIUS,
            query=query,
            data=data,
            enrichment=enrichment_state(edges=_edges_enrichment(completeness, staleness)),
            warnings=(
                _completeness_warnings(completeness)
                + _staleness_warnings(completeness, staleness)
                + _unresolved_warnings(unresolved)
                + overflow_warnings
            ),
        )


def _completeness_warnings(completeness: str) -> list[str]:
    return {
        "NO_SNAPSHOT": ["NO_SNAPSHOT: downstream traversal unavailable; changed set only"],
        "SKIPPED": ["SKIPPED: graph snapshot was skipped; changed set only"],
        "DELTA": ["DELTA: graph snapshot is partial; inspect failed_entities or staleness"],
    }.get(completeness, [])


# ---------------------------------------------------------------------------
# warpline_reverify_worklist_get — warpline.reverify_worklist.v1
# ---------------------------------------------------------------------------
def reverify_worklist(
    repo: Path,
    changed_entity_key_ids: list[int] | None = None,
    depth: int = 2,
    *,
    rev_range: str | None = None,
    changed_refs: Any = None,
    filters: Any = None,
    sort_by: str | None = None,
    sort_order: str | None = None,
    group_by: str | None = None,
    cursor: Any = None,
    limit: int = 100,
    work_client: WorkClient | None = None,
    include_federation: bool = False,
    risk_client: RiskClient | None = None,
    legis_client: LegisClient | None = None,
) -> dict[str, Any]:
    refs = parse_changed_refs(changed_refs)
    with WarplineStore.open(default_store_path(repo)) as store:
        key_ids, resolved, unresolved = _resolve_changed_inputs(
            store,
            repo,
            rev_range=rev_range,
            changed_refs=refs,
            changed_entity_key_ids=changed_entity_key_ids or [],
        )
        result = compute_blast_radius(store, repo, key_ids, depth)
        changed, affected = _enrich_blast(store, repo, result)
        completeness = result["completeness"]
        staleness = result["staleness"]
        items, work_seen, filigree_candidates = render_reverify_worklist(
            changed=changed,
            affected=affected,
            completeness=completeness,
            staleness=staleness,
            work_client=work_client,
        )
        items = apply_filters(items, tool="warpline_reverify_worklist_get", filters=filters)
        items = apply_sort(
            items, tool="warpline_reverify_worklist_get", sort_by=sort_by, sort_order=sort_order
        )
        # group_by buckets the FULL filtered+sorted list (the grouped view is a
        # complete projection, not a page); the flat list still paginates.
        grouped = apply_group_by(items, tool="warpline_reverify_worklist_get", group_by=group_by)
        # include_federation (cross-member SEAM, hub-blessed): consult the members
        # warpline can reach (read-only) over the FULL filtered+sorted worklist —
        # the federation join is a complete projection, not a page. Each consulted
        # member's sub-result carries its OWN weft-reason (PDR-0023 mini-L2): a
        # member with no transport is honestly ``disabled``, never silently dropped.
        federation = (
            consult_federation(
                items,
                work_client=work_client,
                risk_client=risk_client,
                legis_client=legis_client,
            )
            if include_federation
            else None
        )
        items, overflow_warnings, overflow = apply_overflow(
            items, repo=repo, tool="warpline_reverify_worklist_get", schema=SCHEMA_REVERIFY_WORKLIST
        )
        items, page = apply_page(items, limit=limit, cursor=cursor)
        data = {
            "completeness": completeness,
            "staleness": staleness,
            "resolved": resolved,
            "unresolved": unresolved,
            "items": items,
            "grouped": grouped,
            "next_actions": {"filigree": filigree_candidates},
            "overflow": overflow,
            "page": page,
        }
        if federation is not None:
            data["federation"] = federation
        if work_client is None:
            work_state = "unavailable"
        else:
            work_state = "present" if work_seen else "absent"
        query = {
            "repo": str(repo),
            "tool": "warpline_reverify_worklist_get",
            "arguments": {
                "rev_range": rev_range,
                "changed_entity_key_ids": key_ids,
                "depth": depth,
            },
            "filters": _filters_echo(filters),
            "sort": {"by": sort_by or "priority", "order": sort_order or "asc"},
            "group_by": group_by or "none",
            "include_federation": include_federation,
            "page": {"limit": limit, "cursor": cursor},
        }
        return build_envelope(
            SCHEMA_REVERIFY_WORKLIST,
            query=query,
            data=data,
            enrichment=enrichment_state(
                edges=_edges_enrichment(completeness, staleness),
                work=work_state,
            ),
            next_actions={"filigree": filigree_candidates},
            warnings=(
                _completeness_warnings(completeness)
                + _staleness_warnings(completeness, staleness)
                + _unresolved_warnings(unresolved)
                + _federation_warnings(federation)
                + overflow_warnings
            ),
        )


def _federation_warnings(federation: dict[str, Any] | None) -> list[str]:
    """Surface every non-clean per-member federation posture as a FEDERATION
    warning (in addition to the in-band per-member ``weft_reason``), so a member
    that is disabled/unreachable/stale is loud in the warnings stream too — never
    a confident-empty federation block."""

    if not federation:
        return []
    warnings: list[str] = []
    for member, block in federation.get("members", {}).items():
        wr = block.get("weft_reason", {})
        klass = wr.get("reason_class")
        if klass and klass != "clean":
            warnings.append(
                f"FEDERATION: {member} is {klass} — {wr.get('cause')} (fix: {wr.get('fix')})"
            )
    return warnings


# ---------------------------------------------------------------------------
# warpline_edge_snapshot_capture — warpline.edge_snapshot.v1 (only mutating tool)
# ---------------------------------------------------------------------------
def _coerce_max_entities(value: Any) -> int | None:
    """``max_entities`` is an optional positive cap; reject a malformed value
    LOUDLY rather than advertise-and-ignore it (PDR-0023: dead input)."""

    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise InvalidChangedRefsError(
            "max_entities must be a positive integer or null",
            rejected_field="max_entities",
        )
    if value <= 0:
        raise InvalidChangedRefsError(
            "max_entities must be a positive integer or null",
            rejected_field="max_entities",
        )
    return value


def _coerce_if_stale_after(value: Any) -> str | None:
    """``if_stale_after`` is an optional ISO-8601 timestamp; a current snapshot
    captured at-or-after it short-circuits recapture. Reject a non-string."""

    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise InvalidChangedRefsError(
            "if_stale_after must be an ISO-8601 timestamp string or null",
            rejected_field="if_stale_after",
        )
    return value


def capture_snapshot(
    repo: Path,
    commit: str | None = None,
    *,
    mode: str = "full",
    dry_run: bool = False,
    loomweave_command: str | None = None,
    changed_refs: Any = None,
    if_stale_after: Any = None,
    max_entities: Any = None,
    idempotency_key: Any = None,
) -> dict[str, Any]:
    # loomweave_command is server/project config (env), NOT public agent input.
    command = loomweave_command or os.environ.get("WARPLINE_LOOMWEAVE_COMMAND", "loomweave")
    # Consume every advertised input or reject it loudly — no advertise-and-ignore.
    if mode not in {"full", "changed_only"}:
        raise InvalidChangedRefsError(
            "mode must be 'full' or 'changed_only'", rejected_field="mode"
        )
    refs = parse_changed_refs(changed_refs)
    if mode == "changed_only" and not refs:
        raise InvalidChangedRefsError(
            "mode 'changed_only' requires a non-empty changed_refs scope",
            rejected_field="changed_refs",
        )
    cap = _coerce_max_entities(max_entities)
    stale_after = _coerce_if_stale_after(if_stale_after)
    # idempotency_key is an opaque caller-supplied correlation token; echoed back
    # so a caller can tie a response to its request, never silently dropped.
    idem_key = None if idempotency_key is None else str(idempotency_key)

    probe = LoomweaveProbe(repo=repo, command=command).probe()
    status = probe.get("status")
    source_version = str(probe.get("version") or probe.get("reason") or "unknown")
    client = LoomweaveMcpClient(repo=repo, command=command) if status == "available" else None
    scope_locators = (
        {ref["value"] for ref in refs if ref["kind"] in {"locator", "qualname", "path"}}
        if mode == "changed_only"
        else None
    )
    with WarplineStore.open(default_store_path(repo)) as store:
        existing = store.latest_snapshot(repo)
        had_snapshot = existing is not None
        warnings: list[str] = []
        data: dict[str, Any]
        # if_stale_after: a current snapshot captured at-or-after the watermark is
        # fresh enough; honor the short-circuit instead of blindly recapturing.
        if (
            not dry_run
            and stale_after is not None
            and existing is not None
            and str(existing.get("captured_at") or "") >= stale_after
        ):
            data = {
                "snapshot_id": existing.get("id"),
                "commit_sha": existing.get("commit_sha"),
                "source": existing.get("source"),
                "source_version": existing.get("source_version"),
                "completeness": existing.get("completeness"),
                "entities": 0,
                "edges": 0,
                "failed_entities": [],
                "idempotency": "already_current",
                "idempotency_key": idem_key,
            }
            warnings.append(
                f"FRESH: existing snapshot captured at {existing.get('captured_at')} is at or "
                f"after if_stale_after={stale_after}; recapture skipped"
            )
        elif dry_run:
            completeness = "FULL" if client is not None else "SKIPPED"
            data = {
                "snapshot_id": None,
                "commit_sha": commit,
                "source": "loomweave",
                "source_version": source_version,
                "completeness": completeness,
                "entities": 0,
                "edges": 0,
                "failed_entities": [],
                "idempotency": "dry_run",
                "idempotency_key": idem_key,
            }
        else:
            result = capture_edge_snapshot(
                store,
                repo,
                commit_sha=commit,
                client=client,
                source_version=source_version,
                scope_locators=scope_locators,
                max_entities=cap,
            )
            result["idempotency"] = "already_current" if had_snapshot else "created"
            result.pop("query", None)
            result.pop("enrichment", None)
            if result.get("capped"):
                warnings.append(
                    f"CAPPED: max_entities={cap} limited the captured entity set; completeness "
                    "downgraded to DELTA (affected-set is not complete)"
                )
            data = {
                "snapshot_id": result.get("snapshot_id"),
                "commit_sha": result.get("commit_sha"),
                "source": result.get("source"),
                "source_version": result.get("source_version"),
                "completeness": result.get("completeness"),
                "entities": result.get("entities", 0),
                "edges": result.get("edges", 0),
                "failed_entities": result.get("failed_entities", []),
                "idempotency": result["idempotency"],
                "idempotency_key": idem_key,
            }
        edges_state = _EDGES_FOR_COMPLETENESS.get(str(data["completeness"]), "absent")
        # capture touches the SEI authority (loomweave). When it is unreachable,
        # the SEI fact is unavailable (peer down) — never an implied clean state.
        sei_state = "unavailable" if client is None else "absent"
        query = {
            "repo": str(repo),
            "tool": "warpline_edge_snapshot_capture",
            "arguments": {
                "commit": commit,
                "mode": mode,
                "dry_run": dry_run,
                "changed_refs": refs,
                "if_stale_after": stale_after,
                "max_entities": cap,
                "idempotency_key": idem_key,
            },
            "filters": {},
            "sort": {},
            "page": {"limit": None, "cursor": None},
        }
        return build_envelope(
            SCHEMA_EDGE_SNAPSHOT,
            query=query,
            data=data,
            enrichment=enrichment_state(edges=edges_state, sei=sei_state),
            warnings=_completeness_warnings(str(data["completeness"])) + warnings,
        )
