from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from heddle.propagation import blast_radius as compute_blast_radius
from heddle.reverify import render_reverify_worklist
from heddle.store import HeddleStore, default_store_path


def _rev_range_commits(repo: Path, rev_range: str | None) -> set[str] | None:
    if rev_range is None:
        return None
    proc = subprocess.run(
        ["git", "rev-list", rev_range],
        cwd=repo,
        check=True,
        text=True,
        capture_output=True,
    )
    return {line for line in proc.stdout.splitlines() if line}


def _entity_key_id(event: dict[str, object]) -> int | None:
    value = event.get("entity_key_id")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None


def changed(repo: Path, rev_range: str | None = None) -> dict[str, Any]:
    commit_shas = _rev_range_commits(repo, rev_range)
    with HeddleStore.open(default_store_path(repo)) as store:
        changed_events = store.list_change_events(repo, commit_shas=commit_shas)
        changed_entity_key_ids = sorted(
            {
                key_id
                for event in changed_events
                if (key_id := _entity_key_id(event)) is not None
            }
        )
        return {
            "heddle_schema_version": store.schema_version(),
            "query": "changed",
            "rev_range": rev_range,
            "changed": changed_events,
            "changed_entity_key_ids": changed_entity_key_ids,
            "next_actions": {
                "reverify": {
                    "tool": "reverify",
                    "arguments": {
                        "repo": str(repo),
                        "changed_entity_key_ids": changed_entity_key_ids,
                        "depth": 2,
                    },
                }
            },
            "enrichment": {"sei": "absent", "edges": "absent"},
        }


def timeline(repo: Path, entity: str) -> dict[str, Any]:
    with HeddleStore.open(default_store_path(repo)) as store:
        return {
            "heddle_schema_version": store.schema_version(),
            "query": "timeline",
            "entity": entity,
            "events": store.timeline(repo, entity),
            "enrichment": {"sei": "absent", "edges": "absent"},
        }


def blast_radius(
    repo: Path, changed_entity_key_ids: list[int], depth: int = 2
) -> dict[str, Any]:
    with HeddleStore.open(default_store_path(repo)) as store:
        return {
            "heddle_schema_version": store.schema_version(),
            "query": "blast_radius",
            **compute_blast_radius(store, repo, changed_entity_key_ids, depth),
        }


def reverify(repo: Path, changed_entity_key_ids: list[int], depth: int = 2) -> dict[str, Any]:
    result = blast_radius(repo, changed_entity_key_ids, depth)
    return {
        "heddle_schema_version": result["heddle_schema_version"],
        "query": "reverify",
        **render_reverify_worklist(result),
    }
