from __future__ import annotations

from heddle.mcp import dispatch


def test_tools_list_contains_changed_and_timeline() -> None:
    response = dispatch({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})
    names = {tool["name"] for tool in response["result"]["tools"]}
    assert {"changed", "timeline"} <= names


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

