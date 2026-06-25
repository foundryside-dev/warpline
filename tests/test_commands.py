from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from warpline import cli
from warpline.store import WarplineStore, default_store_path


def run(cmd: list[str], cwd: Path) -> str:
    return subprocess.run(cmd, cwd=cwd, check=True, text=True, stdout=subprocess.PIPE).stdout


def test_cli_changed_outputs_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    assert cli.main(["changed", "--repo", str(repo), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema"] == "warpline.change_list.v1"
    assert payload["query"]["tool"] == "warpline_change_list"
    assert isinstance(payload["data"]["items"], list)
    assert "warpline_reverify_worklist_get" in payload["next_actions"]
    assert payload["meta"]["local_only"] is True
    assert payload["meta"]["peer_side_effects"] == []


def test_cli_timeline_outputs_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    assert cli.main(["timeline", "--repo", str(repo), "--entity", "file:a.py", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema"] == "warpline.entity_timeline.v1"
    assert payload["query"]["tool"] == "warpline_entity_timeline_get"
    assert payload["data"]["entity"]["locator"] == "file:a.py"
    assert payload["data"]["entity"]["sei_resolution"] == "unknown"


def test_cli_capture_snapshot_degrades_without_loomweave(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    run(["git", "init"], repo)
    run(["git", "config", "user.email", "agent@example.test"], repo)
    run(["git", "config", "user.name", "Agent"], repo)
    (repo / "app.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    run(["git", "add", "app.py"], repo)
    run(["git", "commit", "-m", "add app"], repo)
    with WarplineStore.open(default_store_path(repo)) as store:
        store.ensure_repo(repo)

    assert (
        cli.main(
            [
                "capture-snapshot",
                "--repo",
                str(repo),
                "--commit",
                "c1",
                "--loomweave-command",
                "/no/such/loomweave",
                "--json",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema"] == "warpline.edge_snapshot.v1"
    assert payload["query"]["tool"] == "warpline_edge_snapshot_capture"
    assert payload["data"]["completeness"] == "SKIPPED"
    assert payload["data"]["source_version"] == "command_unavailable"
    assert payload["meta"]["peer_side_effects"] == []


def test_cli_capture_snapshot_preserves_prior_when_loomweave_absent(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """When loomweave is unavailable at re-capture but a usable prior FULL
    snapshot already describes this commit, the capture must preserve it (not
    downgrade to SKIPPED) and surface a PRESERVED warning. The stored graph and
    its edges survive; read tools keep seeing FULL."""
    repo = tmp_path / "repo"
    repo.mkdir()
    with WarplineStore.open(default_store_path(repo)) as store:
        repo_id = store.ensure_repo(repo)
        a = store.ensure_entity_key(
            repo_id, locator="python:function:a", sei=None, commit_sha="c1"
        )
        b = store.ensure_entity_key(
            repo_id, locator="python:function:b", sei=None, commit_sha="c1"
        )
        prior_id = store.create_edge_snapshot(repo_id, "c1", "loomweave", "v1", "FULL")
        store.append_snapshot_edge(
            prior_id,
            source_entity_key_id=a,
            target_entity_key_id=b,
            edge_kind="calls",
            confidence="resolved",
        )

    assert (
        cli.main(
            [
                "capture-snapshot",
                "--repo",
                str(repo),
                "--commit",
                "c1",
                "--loomweave-command",
                "/no/such/loomweave",
                "--json",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["data"]["completeness"] == "FULL"
    assert payload["data"]["edges"] == 0
    assert payload["data"]["snapshot_id"] == prior_id
    assert any(w.startswith("PRESERVED:") for w in payload["warnings"])
    # enrichment honesty: the graph is real (present), the SEI peer was down.
    assert payload["enrichment"]["edges"] == "present"
    assert payload["enrichment"]["sei"] == "unavailable"

    # The stored FULL snapshot and its edge are untouched.
    with WarplineStore.open(default_store_path(repo)) as store:
        after = store.latest_snapshot(repo)
        assert after is not None
        assert int(after["id"]) == prior_id
        assert after["completeness"] == "FULL"
        assert len(store.snapshot_edges(prior_id)) == 1


def test_cli_backfill_with_resolve_sei_degrades_without_loomweave(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    run(["git", "init"], repo)
    run(["git", "config", "user.email", "agent@example.test"], repo)
    run(["git", "config", "user.name", "Agent"], repo)
    (repo / "app.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    run(["git", "add", "app.py"], repo)
    run(["git", "commit", "-m", "add app"], repo)

    assert (
        cli.main(
            [
                "backfill",
                "--repo",
                str(repo),
                "--resolve-sei",
                "--loomweave-command",
                "/no/such/loomweave",
                "--json",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["commits"] == 1
    assert payload["sei"] == {"resolved": 0, "absent": 0}
    assert payload["sei_resolution"] == {
        "status": "skipped",
        "reason": "command_unavailable",
    }


def test_cli_mcp_smoke_exercises_stdio_server(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    run(["git", "init"], repo)

    assert cli.main(["mcp-smoke", "--repo", str(repo), "--json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["schema"] == "warpline.mcp_smoke.v1"
    assert payload["ok"] is True
    check_names = {check["name"] for check in payload["checks"]}
    assert {
        "initialize_spec_complete",
        "tools_list_available",
        "changed_call_returns_payload",
        "bad_tool_error_structured",
        "server_survives_after_tool_error",
    } <= check_names
