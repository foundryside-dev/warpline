from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, NamedTuple

from warpline.locators import python_entity_locators
from warpline.loomweave import ToolClient, resolve_sei_for_locator
from warpline.store import WarplineStore


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


class _Anchor(NamedTuple):
    """Working-context anchor for one detection call (Rung 1b).

    ``branch``/``head_sha`` are git's own values (no minted identifier), and
    ``detected_at`` is a clock reading; warpline owns only the contract of
    recording them. ``context`` is the honest E4/M8 signal:
    ``clean`` / ``working_tree_dirty`` / ``detached_head``.
    """

    branch: str | None
    head_sha: str | None
    detected_at: str
    context: str


def _git_optional(repo: Path, args: list[str]) -> str | None:
    """Run a git command that is allowed to exit non-zero (returns None then)."""

    result = subprocess.run(
        ["git", *args], cwd=repo, check=False, text=True, capture_output=True
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _detect_anchor(repo: Path) -> _Anchor:
    """Compute the working-context anchor once, at detection time.

    Detached HEAD → ``branch=None`` + ``context='detached_head'``. A dirty work
    tree → ``context='working_tree_dirty'`` (honest E4 signal; the recorded
    ``head_sha`` is the committed HEAD, which is stable, but the working tree
    that produced the detection is not — so the context flags it rather than
    emitting a false-precise clean anchor). Otherwise ``context='clean'``.
    """

    detected_at = datetime.now(UTC).isoformat()
    head_sha = _git_optional(repo, ["rev-parse", "HEAD"])
    branch = _git_optional(repo, ["symbolic-ref", "--short", "-q", "HEAD"])
    # ``--untracked-files=no``: a dirty signal means UNCOMMITTED TRACKED changes,
    # the real "the working tree that produced this detection is unstable" risk
    # (E4). Untracked files (notably warpline's own ``.weft/warpline/`` runtime
    # tree) are not part of what was detected and must not flip the signal.
    dirty = bool(_git_optional(repo, ["status", "--porcelain", "--untracked-files=no"]))
    if branch is None:
        context = "detached_head"
    elif dirty:
        context = "working_tree_dirty"
    else:
        context = "clean"
    return _Anchor(
        branch=branch, head_sha=head_sha, detected_at=detected_at, context=context
    )


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
    store: WarplineStore,
    repo: Path,
    since: str | None = None,
    sei_client: ToolClient | None = None,
) -> dict[str, Any]:
    repo_id = store.ensure_repo(repo)
    count = 0
    sei_stats = {"resolved": 0, "absent": 0}
    # B3: backfill is RECONSTRUCTION, not DETECTION — it cannot know the working
    # context that introduced a historical commit. It therefore passes NO anchor
    # kwargs, so all four v2 anchor columns stay NULL (reads as ``unavailable``,
    # not a false clean/detected signal).
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
    store: WarplineStore,
    repo: Path,
    sha: str,
    sei_client: ToolClient | None = None,
) -> dict[str, Any]:
    repo_id = store.ensure_repo(repo)
    resolved = _git(repo, ["rev-parse", sha]).strip()
    meta = _commit_meta(repo, resolved)
    store.upsert_commit(repo_id, meta)
    # Working-context anchor (Rung 1b): the detection act, computed ONCE per
    # ingest call and threaded onto every change_event it writes.
    anchor = _detect_anchor(repo)
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
                detected_branch=anchor.branch,
                detected_head_sha=anchor.head_sha,
                detected_at=anchor.detected_at,
                detected_context=anchor.context,
            )
            changed += 1
    return {"commit": resolved, "changes": changed, "sei": sei_stats}
