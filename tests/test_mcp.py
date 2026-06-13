from __future__ import annotations

import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from heddle.git import backfill
from heddle.mcp import dispatch
from heddle.mcp import main as mcp_main
from heddle.store import HeddleStore, default_store_path


def run(cmd: list[str], cwd: Path) -> str:
    return subprocess.run(cmd, cwd=cwd, check=True, text=True, stdout=subprocess.PIPE).stdout


def tool_payload(response: dict[str, object]) -> dict[str, object]:
    result = response["result"]
    assert isinstance(result, dict)
    content = result["content"]
    assert isinstance(content, list)
    first = content[0]
    assert isinstance(first, dict)
    return json.loads(str(first["text"]))


def test_tools_list_contains_changed_and_timeline() -> None:
    response = dispatch({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})
    tools = response["result"]["tools"]
    names = {tool["name"] for tool in tools}
    # short shims
    assert {"changed", "timeline", "blast_radius", "reverify", "capture_snapshot"} <= names
    # endorsed names live ALONGSIDE the shims (both must be present, identical schema)
    assert {
        "heddle_change_list",
        "heddle_entity_timeline_get",
        "heddle_entity_churn_count_get",
        "heddle_impact_radius_get",
        "heddle_reverify_worklist_get",
        "heddle_edge_snapshot_capture",
    } <= names
    for tool in tools:
        assert "inputSchema" in tool
        output_schema = tool["outputSchema"]
        assert "outputSchema" in tool
        assert output_schema["required"] == [
            "schema",
            "ok",
            "query",
            "data",
            "warnings",
            "next_actions",
            "enrichment",
            "meta",
        ]
        metadata = tool["metadata"]
        assert metadata["requires_repo"] is True
        assert metadata["local_only"] is True
        assert metadata["peer_side_effects"] == []
        assert isinstance(metadata["idempotent"], bool)
        assert isinstance(metadata["writes_local_state"], bool)
        assert ".weft/heddle/" in metadata["mutates_paths"]


def test_endorsed_and_shim_return_identical_schema_and_data(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    run(["git", "init"], repo)

    def call(name: str) -> dict[str, object]:
        return tool_payload(
            dispatch(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {"name": name, "arguments": {"repo": str(repo)}},
                }
            )
        )

    endorsed = call("heddle_change_list")
    shim = call("changed")
    assert endorsed["schema"] == shim["schema"] == "heddle.change_list.v1"
    assert endorsed["data"] == shim["data"]


def test_capture_snapshot_metadata_exposes_local_write_and_loomweave_dependency() -> None:
    response = dispatch({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})
    tools = response["result"]["tools"]
    capture_snapshot = next(tool for tool in tools if tool["name"] == "capture_snapshot")
    metadata = capture_snapshot["metadata"]
    assert metadata["read_only"] is False
    assert metadata["writes_local_state"] is True
    assert metadata["idempotent"] is True
    assert metadata["federation_dependencies"] == ["loomweave"]


def test_unknown_tool_is_structured_error() -> None:
    response = dispatch(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "missing", "arguments": {}},
        }
    )
    assert response["error"]["code"] == -32601
    assert "missing" in response["error"]["message"]


def test_bad_tool_arguments_are_structured_error() -> None:
    response = dispatch(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "changed", "arguments": {}},
        }
    )
    assert response["error"]["code"] == -32602
    assert response["error"]["message"] == "invalid params"
    data = response["error"]["data"]
    assert data["schema"] == "heddle.error.v1"
    assert data["error_code"] == "missing_required_field"
    assert data["retryability"] == "retry_with_changes"
    assert data["rejected_field"] == "repo"
    assert data["details"]["message"] == "repo is required and must be a non-empty string"


def test_initialize_is_spec_complete() -> None:
    response = dispatch(
        {
            "jsonrpc": "2.0",
            "id": 10,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "pytest", "version": "0"},
            },
        }
    )
    result = response["result"]
    assert result["protocolVersion"] == "2025-03-26"
    assert result["serverInfo"]["name"] == "heddle"
    assert result["serverInfo"]["version"]
    assert result["capabilities"] == {"tools": {}}


def test_mcp_main_degrades_malformed_json_and_continues(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        "sys.stdin",
        io.StringIO(
            '{bad json\n{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}\n'
        ),
    )

    assert mcp_main() == 0

    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert lines[0]["error"]["code"] == -32700
    assert lines[1]["result"]["tools"]


def test_mcp_stdio_tool_error_is_structured_and_server_continues(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    run(["git", "init"], repo)
    requests = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "pytest", "version": "0"},
            },
        },
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "changed",
                "arguments": {"repo": str(repo), "rev_range": "not-a-rev"},
            },
        },
        {"jsonrpc": "2.0", "id": 3, "method": "tools/list", "params": {}},
    ]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
    proc = subprocess.run(
        [sys.executable, "-c", "from heddle.mcp import main; raise SystemExit(main())"],
        input="\n".join(json.dumps(request) for request in requests) + "\n",
        text=True,
        capture_output=True,
        env=env,
        check=True,
        timeout=10,
    )
    responses = [json.loads(line) for line in proc.stdout.splitlines()]
    assert responses[0]["result"]["protocolVersion"] == "2025-03-26"
    assert responses[1]["error"]["code"] == -32602
    assert responses[1]["error"]["data"]["schema"] == "heddle.error.v1"
    assert responses[1]["error"]["data"]["error_code"] == "invalid_rev_range"
    assert responses[1]["error"]["data"]["rejected_field"] == "rev_range"
    assert responses[2]["result"]["tools"]


def test_changed_response_feeds_reverify_in_two_tool_calls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    repo = tmp_path / "repo"
    repo.mkdir()
    run(["git", "init"], repo)
    run(["git", "config", "user.email", "agent@example.test"], repo)
    run(["git", "config", "user.name", "Agent"], repo)
    (repo / "app.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    run(["git", "add", "app.py"], repo)
    run(["git", "commit", "-m", "add app"], repo)

    with HeddleStore.open(default_store_path(repo)) as store:
        backfill(store, repo)

    changed_response = dispatch(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "changed", "arguments": {"repo": str(repo)}},
        }
    )
    changed = tool_payload(changed_response)
    assert changed["schema"] == "heddle.change_list.v1"
    assert changed["ok"] is True
    next_actions = changed["next_actions"]
    assert isinstance(next_actions, dict)
    reverify_action = next_actions["heddle_reverify_worklist_get"]
    assert isinstance(reverify_action, dict)

    reverify_response = dispatch(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "reverify",
                "arguments": reverify_action["arguments"],
            },
        }
    )
    reverify = tool_payload(reverify_response)
    assert reverify["schema"] == "heddle.reverify_worklist.v1"
    assert reverify["ok"] is True
    assert reverify["data"]["completeness"] == "NO_SNAPSHOT"


def test_capture_snapshot_mcp_degrades_without_loomweave(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()

    # loomweave_command is no longer a public agent input (freeze precondition);
    # a repo with no loomweave index degrades to SKIPPED honestly.
    response = dispatch(
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "capture_snapshot",
                "arguments": {"repo": str(repo), "commit": "c1"},
            },
        }
    )
    payload = tool_payload(response)
    assert payload["schema"] == "heddle.edge_snapshot.v1"
    assert payload["ok"] is True
    assert payload["data"]["completeness"] == "SKIPPED"
    assert payload["meta"]["peer_side_effects"] == []
    assert payload["warnings"] == ["SKIPPED: graph snapshot was skipped; changed set only"]
