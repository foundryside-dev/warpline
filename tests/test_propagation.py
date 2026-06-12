from __future__ import annotations

import subprocess
from pathlib import Path

from heddle.propagation import blast_radius
from heddle.store import HeddleStore


def test_blast_radius_returns_no_snapshot_honestly(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    with HeddleStore.open(tmp_path / "heddle.db") as store:
        repo_id = store.ensure_repo(repo)
        key = store.ensure_entity_key(repo_id, locator="file:a.py", sei=None, commit_sha="c1")
        result = blast_radius(store, repo, [key], depth=2)
    assert result["completeness"] == "NO_SNAPSHOT"
    assert result["affected"] == []


def test_blast_radius_walks_downstream(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    with HeddleStore.open(tmp_path / "heddle.db") as store:
        repo_id = store.ensure_repo(repo)
        a = store.ensure_entity_key(
            repo_id, locator="python:function:a", sei=None, commit_sha="c1"
        )
        b = store.ensure_entity_key(
            repo_id, locator="python:function:b", sei=None, commit_sha="c1"
        )
        snap = store.create_edge_snapshot(repo_id, "c1", "loomweave", "test", "FULL")
        store.append_snapshot_edge(
            snap,
            source_entity_key_id=a,
            target_entity_key_id=b,
            edge_kind="calls",
            confidence="resolved",
        )
        result = blast_radius(store, repo, [a], depth=2)
    assert result["completeness"] == "FULL"
    assert result["affected"][0]["entity_key_id"] == b
    assert result["affected"][0]["depth"] == 1


def test_blast_radius_reports_snapshot_staleness(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "agent@example.test"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Agent"], cwd=repo, check=True)
    (repo / "a.py").write_text("a = 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "a.py"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "one"], cwd=repo, check=True)
    first = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    ).stdout.strip()
    (repo / "a.py").write_text("a = 2\n", encoding="utf-8")
    subprocess.run(["git", "commit", "-am", "two"], cwd=repo, check=True)

    with HeddleStore.open(tmp_path / "heddle.db") as store:
        repo_id = store.ensure_repo(repo)
        key = store.ensure_entity_key(repo_id, locator="file:a.py", sei=None, commit_sha=first)
        store.create_edge_snapshot(repo_id, first, "loomweave", "test", "FULL")
        result = blast_radius(store, repo, [key], depth=2)
    assert result["staleness"]["snapshot_commit"] == first
    assert result["staleness"]["commits_behind"] == 1
