from __future__ import annotations

import subprocess
from pathlib import Path

from heddle.git import backfill
from heddle.store import HeddleStore


def run(cmd: list[str], cwd: Path) -> str:
    return subprocess.run(cmd, cwd=cwd, check=True, text=True, stdout=subprocess.PIPE).stdout


def test_backfill_records_file_change(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    run(["git", "init"], repo)
    run(["git", "config", "user.email", "agent@example.test"], repo)
    run(["git", "config", "user.name", "Agent"], repo)
    (repo / "app.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    run(["git", "add", "app.py"], repo)
    run(["git", "commit", "-m", "add app"], repo)

    with HeddleStore.open(tmp_path / "heddle.db") as store:
        report = backfill(store, repo)
        events = store.list_change_events(repo)

    assert report["commits"] == 1
    assert len(events) == 1
    assert events[0]["path"] == "app.py"
    assert events[0]["change_kind"] == "added"
    assert events[0]["actor"] == "Agent <agent@example.test>"


def test_backfill_is_idempotent(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    run(["git", "init"], repo)
    run(["git", "config", "user.email", "agent@example.test"], repo)
    run(["git", "config", "user.name", "Agent"], repo)
    (repo / "app.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    run(["git", "add", "app.py"], repo)
    run(["git", "commit", "-m", "add app"], repo)

    with HeddleStore.open(tmp_path / "heddle.db") as store:
        backfill(store, repo)
        backfill(store, repo)
        assert len(store.list_change_events(repo)) == 1


def test_backfill_degrades_undecodable_python_file_to_file_locator(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    run(["git", "init"], repo)
    run(["git", "config", "user.email", "agent@example.test"], repo)
    run(["git", "config", "user.name", "Agent"], repo)
    (repo / "bad.py").write_bytes(b"def ok():\n    return '\xff'\n")
    run(["git", "add", "bad.py"], repo)
    run(["git", "commit", "-m", "add undecodable source"], repo)

    with HeddleStore.open(tmp_path / "heddle.db") as store:
        report = backfill(store, repo)
        events = store.list_change_events(repo)

    assert report["commits"] == 1
    assert events[0]["locator"] == "file:bad.py"
