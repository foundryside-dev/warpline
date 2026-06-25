from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Protocol

from warpline.loomweave import loomweave_entity_id_candidates
from warpline.store import WarplineStore


class NeighborhoodClient(Protocol):
    def neighborhood(self, entity: str) -> dict[str, Any]:
        ...


def _as_int(value: object) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value)
    raise TypeError(f"expected integer-compatible value, got {type(value).__name__}")


def _resolve_commit(repo: Path, commit: str | None) -> str:
    rev = commit if commit is not None else "HEAD"
    proc = subprocess.run(
        ["git", "rev-parse", "--verify", f"{rev}^{{commit}}"],
        cwd=repo,
        check=False,
        text=True,
        capture_output=True,
    )
    if proc.returncode != 0:
        return commit if commit is not None else "UNKNOWN"
    return proc.stdout.strip()


def record_skipped_snapshot(
    store: WarplineStore,
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


def capture_edge_snapshot(
    store: WarplineStore,
    repo: Path,
    *,
    commit_sha: str | None = None,
    client: NeighborhoodClient | None,
    source_version: str,
    scope_locators: set[str] | None = None,
    scope_failures: list[dict[str, str]] | None = None,
    max_entities: int | None = None,
) -> dict[str, Any]:
    repo_id = store.ensure_repo(repo)
    resolved_commit = _resolve_commit(repo, commit_sha)
    if client is None:
        prior = store.get_edge_snapshot(repo_id, resolved_commit, "loomweave")
        if prior is not None and prior.get("completeness") in {"FULL", "DELTA"}:
            # Loomweave is absent at re-capture, but a usable prior snapshot
            # already describes this immutable commit. Overwriting it with a
            # 0-edge SKIPPED row would destroy a real edge graph to record "we
            # don't know" — strictly worse than what we already hold, and the
            # same R3 data-loss the atomic capture path was built to prevent.
            # Leave the stored row and its edges untouched; report the recapture
            # as skipped against the preserved snapshot (fail-closed doctrine).
            # A stale FULL/DELTA is still a real graph, so we preserve regardless
            # of staleness — the read path downgrades stale completeness on its
            # own (PDR-0023).
            return {
                "query": "capture_snapshot",
                "commit_sha": resolved_commit,
                "snapshot_id": _as_int(prior["id"]),
                "source": "loomweave",
                "source_version": prior.get("source_version"),
                "completeness": prior.get("completeness"),
                "entities": 0,
                "edges": 0,
                "capped": False,
                "recapture_skipped": True,
                "enrichment": {"edges": "skipped"},
            }
        # No usable prior (none, or a prior already SKIPPED): record the skip in
        # ONE transaction via the atomic path. There is nothing to corrupt, and
        # this retires the old two-commit (UPSERT then DELETE) non-atomic write.
        snapshot_id = store.capture_snapshot_atomic(
            repo_id=repo_id,
            commit_sha=resolved_commit,
            source="loomweave",
            source_version=source_version,
            completeness="SKIPPED",
            edges=[],
        )
        return {
            "query": "capture_snapshot",
            "commit_sha": resolved_commit,
            "snapshot_id": snapshot_id,
            "source": "loomweave",
            "source_version": source_version,
            "completeness": "SKIPPED",
            "entities": 0,
            "edges": 0,
            "capped": False,
            "enrichment": {"edges": "skipped"},
        }

    entity_id_to_key_id: dict[str, int] = {}
    query_entities: list[tuple[str, str]] = []
    for row in store.list_entity_keys(repo):
        locator = row.get("locator")
        key_id = row.get("id")
        if isinstance(locator, str) and isinstance(key_id, int):
            # changed_only scope: only capture edges for the referenced entities.
            if scope_locators is not None and locator not in scope_locators:
                continue
            aliases = _entity_aliases(locator, row.get("sei"))
            for alias in aliases:
                entity_id_to_key_id[alias] = key_id
            query_entities.append((locator, aliases[0]))

    # max_entities: cap the queried set and downgrade completeness — a capped
    # capture is a partial graph and must NOT report itself FULL (PDR-0023).
    query_entities.sort()
    capped = max_entities is not None and len(query_entities) > max_entities
    if capped:
        query_entities = query_entities[:max_entities]

    edge_count = 0
    snapshot_edges: list[tuple[int, int, str, str]] = []
    failures: list[dict[str, str]] = list(scope_failures or [])
    for locator, query_entity in query_entities:
        try:
            neighborhood = client.neighborhood(query_entity)
            edges = edges_from_neighborhood(neighborhood)
        except Exception as exc:
            failures.append({"locator": locator, "reason": str(exc)})
            continue
        for source, target, edge_kind in sorted(edges):
            source_id = _entity_key_id_for_locator(
                store, repo_id, entity_id_to_key_id, source, resolved_commit
            )
            target_id = _entity_key_id_for_locator(
                store, repo_id, entity_id_to_key_id, target, resolved_commit
            )
            snapshot_edges.append((source_id, target_id, edge_kind, "resolved"))
            edge_count += 1
    if scope_locators is not None and not query_entities and not failures:
        failures.append({"locator": "<changed_only_scope>", "reason": "empty_scope"})

    # A capped capture is structurally partial: it is missing entities it knows
    # exist. Treat that exactly like a per-entity failure — DELTA, not FULL.
    # Edges are fully staged above; the snapshot row is written exactly once,
    # atomically, AFTER completeness is known. Any failure raised by the client
    # propagates BEFORE this write, so the prior snapshot stays intact.
    completeness = "DELTA" if (failures or capped) else "FULL"
    snapshot_id = store.capture_snapshot_atomic(
        repo_id=repo_id,
        commit_sha=resolved_commit,
        source="loomweave",
        source_version=source_version,
        completeness=completeness,
        edges=snapshot_edges,
    )

    return {
        "query": "capture_snapshot",
        "commit_sha": resolved_commit,
        "snapshot_id": snapshot_id,
        "source": "loomweave",
        "source_version": source_version,
        "completeness": completeness,
        "entities": len(query_entities),
        "edges": edge_count,
        "failed_entities": failures,
        "capped": capped,
        "enrichment": {"edges": "partial" if (failures or capped) else "present"},
    }


def _entity_key_id_for_locator(
    store: WarplineStore,
    repo_id: str,
    locator_to_id: dict[str, int],
    locator: str,
    commit_sha: str,
) -> int:
    if locator in locator_to_id:
        return locator_to_id[locator]
    key_id = store.ensure_entity_key(repo_id, locator=locator, sei=None, commit_sha=commit_sha)
    locator_to_id[locator] = key_id
    return key_id


def _entity_aliases(locator: str, sei: object) -> list[str]:
    aliases = loomweave_entity_id_candidates(locator)
    if isinstance(sei, str) and sei:
        aliases.append(sei)
    deduped: list[str] = []
    for alias in aliases:
        if alias not in deduped:
            deduped.append(alias)
    return deduped


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
