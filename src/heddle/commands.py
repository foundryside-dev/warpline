from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

from heddle.envelope import build_envelope, enrichment_state
from heddle.errors import BadRevisionError
from heddle.loomweave import LoomweaveMcpClient, LoomweaveProbe
from heddle.propagation import blast_radius as compute_blast_radius
from heddle.refs import (
    changed_ref_for_row,
    entity_view,
    parse_changed_refs,
    parse_entity_ref,
)
from heddle.reverify import render_reverify_worklist
from heddle.siblings import RenameFeed, WorkClient
from heddle.snapshot import capture_edge_snapshot
from heddle.store import HeddleStore, default_store_path

# FROZEN schema URIs (one contract per tool; endorsed name and shim share it).
SCHEMA_CHANGE_LIST = "heddle.change_list.v1"
SCHEMA_ENTITY_TIMELINE = "heddle.entity_timeline.v1"
SCHEMA_ENTITY_CHURN_COUNT = "heddle.entity_churn_count.v1"
SCHEMA_IMPACT_RADIUS = "heddle.impact_radius.v1"
SCHEMA_REVERIFY_WORKLIST = "heddle.reverify_worklist.v1"
SCHEMA_EDGE_SNAPSHOT = "heddle.edge_snapshot.v1"

# enrichment.edges value for each completeness level.
_EDGES_FOR_COMPLETENESS = {
    "FULL": "present",
    "DELTA": "partial",
    "NO_SNAPSHOT": "absent",
    "SKIPPED": "skipped",
}


def session_context(repo: Path) -> str:
    """A one-line temporal snapshot for the SessionStart hook (fail-soft)."""

    try:
        with HeddleStore.open(default_store_path(repo)) as store:
            events = store.list_change_events(repo)
            snapshot = store.latest_snapshot(repo)
    except Exception:
        return "heddle: temporal store unavailable"
    if not events:
        return "heddle: 0 change events tracked (run `heddle backfill`)"
    if snapshot is None or snapshot.get("completeness") == "SKIPPED":
        snap = "no edge snapshot (impact/reverify return NO_SNAPSHOT until capture)"
    else:
        snap = f"snapshot {snapshot.get('completeness')} @ {str(snapshot.get('commit_sha'))[:8]}"
    return f"heddle: {len(events)} change events tracked; {snap}"


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


def _as_int(value: object) -> int:
    assert isinstance(value, int)
    return value


def _resolved_key_ids(
    store: HeddleStore,
    repo: Path,
    *,
    rev_range: str | None,
    changed_refs: list[dict[str, str]],
    changed_entity_key_ids: list[int],
) -> list[int]:
    ids: set[int] = set(changed_entity_key_ids)
    for ref in changed_refs:
        row = store.resolve_ref(repo, ref["kind"], ref["value"])
        if row is not None:
            ids.add(_as_int(row["id"]))
    if rev_range is not None:
        commit_shas = _rev_range_commits(repo, rev_range)
        for event in store.list_change_events(repo, commit_shas=commit_shas):
            key_id = event.get("entity_key_id")
            if isinstance(key_id, int):
                ids.add(key_id)
    return sorted(ids)


# ---------------------------------------------------------------------------
# heddle_change_list — heddle.change_list.v1
# ---------------------------------------------------------------------------
def change_list(
    repo: Path,
    rev_range: str | None = None,
    *,
    limit: int = 50,
) -> dict[str, Any]:
    commit_shas = _rev_range_commits(repo, rev_range)
    with HeddleStore.open(default_store_path(repo)) as store:
        events = store.list_change_events(repo, commit_shas=commit_shas)
        items: list[dict[str, Any]] = []
        changed_refs: list[dict[str, str]] = []
        seen_refs: set[tuple[str, str]] = set()
        key_ids: list[int] = []
        has_sei = False
        for event in events[:limit]:
            path = str(event.get("path"))
            view = entity_view(event, include_key_id=True, path=path)
            if view["sei"]:
                has_sei = True
            items.append(
                {
                    "change_id": f"heddle:change:{event.get('change_event_id')}",
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

        data = {
            "items": items,
            "changed_refs": changed_refs,
            "page": {"limit": limit, "next_cursor": None, "has_more": len(events) > limit},
        }
        next_actions = {
            "heddle_reverify_worklist_get": {
                "tool": "heddle_reverify_worklist_get",
                "arguments": {
                    "repo": str(repo),
                    "changed_entity_key_ids": key_ids,
                    "changed_refs": changed_refs,
                    "depth": 2,
                },
            },
            "heddle_impact_radius_get": {
                "tool": "heddle_impact_radius_get",
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
            "tool": "heddle_change_list",
            "arguments": {"rev_range": rev_range},
            "filters": {},
            "sort": {"by": "changed_at", "order": "asc"},
            "page": {"limit": limit, "cursor": None},
        }
        return build_envelope(
            SCHEMA_CHANGE_LIST,
            query=query,
            data=data,
            enrichment=enrichment_state(sei="present" if has_sei else "absent"),
            next_actions=next_actions,
        )


# ---------------------------------------------------------------------------
# heddle_entity_timeline_get — heddle.entity_timeline.v1
# ---------------------------------------------------------------------------
def entity_timeline(
    repo: Path,
    entity: Any,
    *,
    limit: int = 50,
    rename_feed: RenameFeed | None = None,
) -> dict[str, Any]:
    ref = parse_entity_ref(entity)
    value = ref["value"]
    with HeddleStore.open(default_store_path(repo)) as store:
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
            for row in rows[:limit]
        ]
        data = {"entity": entity_out, "items": items, "page": _page(limit)}
        query = {
            "repo": str(repo),
            "tool": "heddle_entity_timeline_get",
            "arguments": {"entity_ref": ref},
            "filters": {},
            "sort": {"by": "changed_at", "order": "asc"},
            "page": {"limit": limit, "cursor": None},
        }
        return build_envelope(
            SCHEMA_ENTITY_TIMELINE,
            query=query,
            data=data,
            enrichment=enrichment_state(
                sei="present" if entity_out["sei"] else "absent",
                governance="present" if rename_feed is not None else "unavailable",
            ),
        )


# ---------------------------------------------------------------------------
# heddle_entity_churn_count_get — heddle.entity_churn_count.v1 (NEW)
# ---------------------------------------------------------------------------
def entity_churn_count(
    repo: Path,
    entity_refs: Any,
    *,
    window: dict[str, Any] | None = None,
    sort_by: str = "churn_count",
    sort_order: str = "desc",
    limit: int = 100,
) -> dict[str, Any]:
    refs = parse_changed_refs(entity_refs)
    window = window or {}
    since = window.get("since")
    until = window.get("until")
    rev_range = window.get("rev_range")
    with HeddleStore.open(default_store_path(repo)) as store:
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
        data = {
            "items": items[:limit],
            "window": {"since": since, "until": until, "rev_range": rev_range},
            "page": _page(limit),
        }
        query = {
            "repo": str(repo),
            "tool": "heddle_entity_churn_count_get",
            "arguments": {"entity_refs": refs, "window": data["window"]},
            "filters": {},
            "sort": {"by": sort_by, "order": sort_order},
            "page": {"limit": limit, "cursor": None},
        }
        return build_envelope(
            SCHEMA_ENTITY_CHURN_COUNT,
            query=query,
            data=data,
            enrichment=enrichment_state(sei="present" if has_sei else "absent"),
        )


def _enrich_blast(
    store: HeddleStore, repo: Path, result: dict[str, Any]
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
# heddle_impact_radius_get — heddle.impact_radius.v1
# ---------------------------------------------------------------------------
def impact_radius(
    repo: Path,
    changed_entity_key_ids: list[int] | None = None,
    depth: int = 2,
    *,
    rev_range: str | None = None,
    changed_refs: Any = None,
    limit: int = 100,
) -> dict[str, Any]:
    refs = parse_changed_refs(changed_refs)
    with HeddleStore.open(default_store_path(repo)) as store:
        key_ids = _resolved_key_ids(
            store,
            repo,
            rev_range=rev_range,
            changed_refs=refs,
            changed_entity_key_ids=changed_entity_key_ids or [],
        )
        result = compute_blast_radius(store, repo, key_ids, depth)
        changed, affected = _enrich_blast(store, repo, result)
        completeness = result["completeness"]
        data = {
            "completeness": completeness,
            "staleness": result["staleness"],
            "changed": changed,
            "affected": affected,
            "page": _page(limit),
        }
        query = {
            "repo": str(repo),
            "tool": "heddle_impact_radius_get",
            "arguments": {
                "rev_range": rev_range,
                "changed_entity_key_ids": key_ids,
                "depth": depth,
            },
            "filters": {},
            "sort": {"by": "depth", "order": "asc"},
            "page": {"limit": limit, "cursor": None},
        }
        return build_envelope(
            SCHEMA_IMPACT_RADIUS,
            query=query,
            data=data,
            enrichment=enrichment_state(
                edges=_EDGES_FOR_COMPLETENESS.get(completeness, "absent")
            ),
            warnings=_completeness_warnings(completeness),
        )


def _completeness_warnings(completeness: str) -> list[str]:
    return {
        "NO_SNAPSHOT": ["NO_SNAPSHOT: downstream traversal unavailable; changed set only"],
        "SKIPPED": ["SKIPPED: graph snapshot was skipped; changed set only"],
        "DELTA": ["DELTA: graph snapshot is partial; inspect failed_entities or staleness"],
    }.get(completeness, [])


# ---------------------------------------------------------------------------
# heddle_reverify_worklist_get — heddle.reverify_worklist.v1
# ---------------------------------------------------------------------------
def reverify_worklist(
    repo: Path,
    changed_entity_key_ids: list[int] | None = None,
    depth: int = 2,
    *,
    rev_range: str | None = None,
    changed_refs: Any = None,
    limit: int = 100,
    work_client: WorkClient | None = None,
) -> dict[str, Any]:
    refs = parse_changed_refs(changed_refs)
    with HeddleStore.open(default_store_path(repo)) as store:
        key_ids = _resolved_key_ids(
            store,
            repo,
            rev_range=rev_range,
            changed_refs=refs,
            changed_entity_key_ids=changed_entity_key_ids or [],
        )
        result = compute_blast_radius(store, repo, key_ids, depth)
        changed, affected = _enrich_blast(store, repo, result)
        items, work_seen, filigree_candidates = render_reverify_worklist(
            changed=changed,
            affected=affected,
            completeness=result["completeness"],
            staleness=result["staleness"],
            work_client=work_client,
        )
        data = {
            "completeness": result["completeness"],
            "staleness": result["staleness"],
            "items": items[:limit],
            "next_actions": {"filigree": filigree_candidates},
            "page": _page(limit),
        }
        if work_client is None:
            work_state = "unavailable"
        else:
            work_state = "present" if work_seen else "absent"
        query = {
            "repo": str(repo),
            "tool": "heddle_reverify_worklist_get",
            "arguments": {
                "rev_range": rev_range,
                "changed_entity_key_ids": key_ids,
                "depth": depth,
            },
            "filters": {},
            "sort": {"by": "priority", "order": "asc"},
            "page": {"limit": limit, "cursor": None},
        }
        return build_envelope(
            SCHEMA_REVERIFY_WORKLIST,
            query=query,
            data=data,
            enrichment=enrichment_state(
                edges=_EDGES_FOR_COMPLETENESS.get(result["completeness"], "absent"),
                work=work_state,
            ),
            next_actions={"filigree": filigree_candidates},
            warnings=_completeness_warnings(result["completeness"]),
        )


# ---------------------------------------------------------------------------
# heddle_edge_snapshot_capture — heddle.edge_snapshot.v1 (only mutating tool)
# ---------------------------------------------------------------------------
def capture_snapshot(
    repo: Path,
    commit: str | None = None,
    *,
    mode: str = "full",
    dry_run: bool = False,
    loomweave_command: str | None = None,
) -> dict[str, Any]:
    # loomweave_command is server/project config (env), NOT public agent input.
    command = loomweave_command or os.environ.get("HEDDLE_LOOMWEAVE_COMMAND", "loomweave")
    probe = LoomweaveProbe(repo=repo, command=command).probe()
    status = probe.get("status")
    source_version = str(probe.get("version") or probe.get("reason") or "unknown")
    client = LoomweaveMcpClient(repo=repo, command=command) if status == "available" else None
    with HeddleStore.open(default_store_path(repo)) as store:
        had_snapshot = store.latest_snapshot(repo) is not None
        data: dict[str, Any]
        if dry_run:
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
            }
        else:
            result = capture_edge_snapshot(
                store, repo, commit_sha=commit, client=client, source_version=source_version
            )
            result["idempotency"] = "already_current" if had_snapshot else "created"
            result.pop("query", None)
            result.pop("enrichment", None)
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
            }
        edges_state = _EDGES_FOR_COMPLETENESS.get(str(data["completeness"]), "absent")
        # capture touches the SEI authority (loomweave). When it is unreachable,
        # the SEI fact is unavailable (peer down) — never an implied clean state.
        sei_state = "unavailable" if client is None else "absent"
        query = {
            "repo": str(repo),
            "tool": "heddle_edge_snapshot_capture",
            "arguments": {"commit": commit, "mode": mode, "dry_run": dry_run},
            "filters": {},
            "sort": {},
            "page": {"limit": None, "cursor": None},
        }
        return build_envelope(
            SCHEMA_EDGE_SNAPSHOT,
            query=query,
            data=data,
            enrichment=enrichment_state(edges=edges_state, sei=sei_state),
            warnings=_completeness_warnings(str(data["completeness"])),
        )
