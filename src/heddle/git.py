from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from heddle.locators import python_entity_locators
from heddle.loomweave import ToolClient, resolve_sei_for_locator
from heddle.store import HeddleStore


def _git(repo: Path, args: list[str]) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        text=True,
        capture_output=True,
    ).stdout


def _git_bytes(repo: Path, args: list[str]) -> bytes:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
    ).stdout


def _change_kind(status: str) -> str:
    return {"A": "added", "M": "modified", "D": "removed", "R": "moved"}.get(
        status[0], "modified"
    )


def _commits(repo: Path, since: str | None = None) -> list[str]:
    args = ["log", "--reverse", "--format=%H"]
    if since:
        args.append(f"{since}..HEAD")
    return [line for line in _git(repo, args).splitlines() if line]


def _commit_meta(repo: Path, sha: str) -> dict[str, str]:
    fmt = "%H%x00%P%x00%an <%ae>%x00%aI%x00%cI"
    raw = _git(repo, ["show", "-s", f"--format={fmt}", sha]).strip()
    commit, parents, author, authored_at, committed_at = raw.split("\x00")
    return {
        "sha": commit,
        "parents_json": json.dumps([p for p in parents.split() if p]),
        "author": author,
        "authored_at": authored_at,
        "committed_at": committed_at,
    }


def _name_status(repo: Path, sha: str) -> list[tuple[str, str]]:
    raw = _git(repo, ["diff-tree", "--root", "--no-commit-id", "--name-status", "-r", sha])
    rows: list[tuple[str, str]] = []
    for line in raw.splitlines():
        parts = line.split("\t")
        if not parts:
            continue
        status = parts[0]
        path = parts[-1]
        rows.append((status, path))
    return rows


def _file_at_commit(repo: Path, sha: str, path: str) -> str | None:
    try:
        return _git_bytes(repo, ["show", f"{sha}:{path}"]).decode("utf-8")
    except (subprocess.CalledProcessError, UnicodeDecodeError):
        return None


def _locators_for_path(repo: Path, sha: str, path: str) -> list[str]:
    if not path.endswith(".py"):
        return [f"file:{path}"]
    source = _file_at_commit(repo, sha, path)
    if source is None:
        return [f"file:{path}"]
    return python_entity_locators(path, source)


def _sei_for_locator(sei_client: ToolClient | None, locator: str) -> str | None:
    if sei_client is None:
        return None
    return resolve_sei_for_locator(sei_client, locator)


def _record_sei_stats(
    stats: dict[str, int],
    sei_client: ToolClient | None,
    sei: str | None,
) -> None:
    if sei_client is None:
        return
    if sei is None:
        stats["absent"] += 1
    else:
        stats["resolved"] += 1


def backfill(
    store: HeddleStore,
    repo: Path,
    since: str | None = None,
    sei_client: ToolClient | None = None,
) -> dict[str, Any]:
    repo_id = store.ensure_repo(repo)
    count = 0
    sei_stats = {"resolved": 0, "absent": 0}
    for sha in _commits(repo, since=since):
        meta = _commit_meta(repo, sha)
        store.upsert_commit(repo_id, meta)
        for status, path in _name_status(repo, sha):
            for locator in _locators_for_path(repo, sha, path):
                sei = _sei_for_locator(sei_client, locator)
                _record_sei_stats(sei_stats, sei_client, sei)
                key_id = store.ensure_entity_key(repo_id, locator=locator, sei=sei, commit_sha=sha)
                store.append_change_event(
                    repo_id=repo_id,
                    entity_key_id=key_id,
                    commit_sha=sha,
                    path=path,
                    change_kind=_change_kind(status),
                    actor=meta["author"],
                    changed_at=meta["authored_at"],
                )
        count += 1
    return {"commits": count, "sei": sei_stats}


def ingest_commit(
    store: HeddleStore,
    repo: Path,
    sha: str,
    sei_client: ToolClient | None = None,
) -> dict[str, Any]:
    repo_id = store.ensure_repo(repo)
    resolved = _git(repo, ["rev-parse", sha]).strip()
    meta = _commit_meta(repo, resolved)
    store.upsert_commit(repo_id, meta)
    changed = 0
    sei_stats = {"resolved": 0, "absent": 0}
    for status, path in _name_status(repo, resolved):
        for locator in _locators_for_path(repo, resolved, path):
            sei = _sei_for_locator(sei_client, locator)
            _record_sei_stats(sei_stats, sei_client, sei)
            key_id = store.ensure_entity_key(
                repo_id,
                locator=locator,
                sei=sei,
                commit_sha=resolved,
            )
            store.append_change_event(
                repo_id=repo_id,
                entity_key_id=key_id,
                commit_sha=resolved,
                path=path,
                change_kind=_change_kind(status),
                actor=meta["author"],
                changed_at=meta["authored_at"],
            )
            changed += 1
    return {"commit": resolved, "changes": changed, "sei": sei_stats}
