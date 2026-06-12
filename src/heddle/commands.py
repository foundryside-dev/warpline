from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

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


def changed(repo: Path, rev_range: str | None = None) -> dict[str, Any]:
    commit_shas = _rev_range_commits(repo, rev_range)
    with HeddleStore.open(default_store_path(repo)) as store:
        return {
            "heddle_schema_version": store.schema_version(),
            "query": "changed",
            "rev_range": rev_range,
            "changed": store.list_change_events(repo, commit_shas=commit_shas),
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
