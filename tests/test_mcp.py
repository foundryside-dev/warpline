from __future__ import annotations

import io
import json
import subprocess
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
    assert {"changed", "timeline", "blast_radius", "reverify"} <= names
    for tool in tools:
        assert "inputSchema" in tool
        output_schema = tool["outputSchema"]
        assert "outputSchema" in tool
        assert output_schema["required"] == ["schema", "ok", "data", "warnings", "meta"]


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
    assert response["error"]["details"]["reason"] == (
        "repo is required and must be a non-empty string"
    )


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
    assert changed["schema"] == "heddle.draft.changed.v1"
    assert changed["ok"] is True
    data = changed["data"]
    assert isinstance(data, dict)
    next_actions = data["next_actions"]
    assert isinstance(next_actions, dict)
    reverify_action = next_actions["reverify"]
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
    assert reverify["schema"] == "heddle.draft.reverify.v1"
    assert reverify["ok"] is True
    assert reverify["data"]["completeness"] == "NO_SNAPSHOT"
