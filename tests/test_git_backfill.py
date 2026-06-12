from __future__ import annotations

import subprocess
from pathlib import Path

from heddle.git import backfill, ingest_commit
from heddle.store import HeddleStore


class FakeSeiClient:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def call_tool(self, name: str, arguments: dict[str, object]) -> dict[str, object]:
        assert name == "entity_resolve"
        qualnames = arguments["qualnames"]
        assert isinstance(qualnames, list)
        locator = str(qualnames[0])
        self.calls.append(locator)
        return {
            "results": [
                {
                    "qualname": locator,
                    "result_kind": "resolved",
                    "candidates": [
                        {
                            "id": locator,
                            "sei": f"loomweave:eid:{locator}",
                        }
                    ],
                }
            ]
        }


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


def test_backfill_optionally_resolves_sei(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    run(["git", "init"], repo)
    run(["git", "config", "user.email", "agent@example.test"], repo)
    run(["git", "config", "user.name", "Agent"], repo)
    (repo / "app.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    run(["git", "add", "app.py"], repo)
    run(["git", "commit", "-m", "add app"], repo)
    client = FakeSeiClient()

    with HeddleStore.open(tmp_path / "heddle.db") as store:
        report = backfill(store, repo, sei_client=client)
        events = store.list_change_events(repo)

    assert report["commits"] == 1
    assert report["sei"] == {"resolved": 1, "absent": 0}
    assert events[0]["sei"] == f"loomweave:eid:{events[0]['locator']}"
    assert client.calls == [events[0]["locator"]]


def test_ingest_commit_optionally_resolves_sei(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    run(["git", "init"], repo)
    run(["git", "config", "user.email", "agent@example.test"], repo)
    run(["git", "config", "user.name", "Agent"], repo)
    (repo / "app.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    run(["git", "add", "app.py"], repo)
    run(["git", "commit", "-m", "add app"], repo)
    client = FakeSeiClient()

    with HeddleStore.open(tmp_path / "heddle.db") as store:
        report = ingest_commit(store, repo, "HEAD", sei_client=client)
        events = store.list_change_events(repo)

    assert report["changes"] == 1
    assert report["sei"] == {"resolved": 1, "absent": 0}
    assert events[0]["sei"] == f"loomweave:eid:{events[0]['locator']}"
