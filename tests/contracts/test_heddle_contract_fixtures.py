from __future__ import annotations

import json
from pathlib import Path

FIXTURES = Path("tests/fixtures/contracts/heddle")


def load(name: str) -> dict[str, object]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_mcp_tool_inventory_is_agent_first_and_enrich_only() -> None:
    fixture = load("mcp-tool-inventory.json")
    assert fixture["schema"] == "heddle.draft.mcp_tool_inventory.v1"
    assert fixture["status"] == "pre-admission-draft"
    tools = fixture["tools"]
    assert isinstance(tools, list)
    names = [tool["name"] for tool in tools if isinstance(tool, dict)]
    assert names == sorted(names)
    assert {"changed", "timeline", "blast_radius", "reverify"} <= set(names)
    for tool in tools:
        assert isinstance(tool, dict)
        assert tool["mutates"] is False
        assert tool["local_only"] is True
        assert tool["peer_side_effects"] == []
        assert tool["authority_boundary"]


def test_changed_response_fixture_carries_enrichment_state() -> None:
    fixture = load("mcp-response-changed.json")
    assert fixture["schema"] == "heddle.draft.changed.v1"
    assert fixture["ok"] is True
    data = fixture["data"]
    assert isinstance(data, dict)
    assert "changed" in data
    enrichment = data["enrichment"]
    assert isinstance(enrichment, dict)
    assert enrichment["sei"] in {"present", "absent"}
    assert enrichment["edges"] in {"present", "absent", "stale"}


def test_reverify_response_fixture_carries_honesty_fields() -> None:
    fixture = load("mcp-response-reverify.json")
    data = fixture["data"]
    assert isinstance(data, dict)
    assert fixture["schema"] == "heddle.draft.reverify.v1"
    assert data["completeness"] in {"FULL", "DELTA", "NO_SNAPSHOT", "SKIPPED"}
    assert "staleness" in data
    assert "worklist" in data
