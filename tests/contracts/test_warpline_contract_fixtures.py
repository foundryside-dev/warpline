from __future__ import annotations

import json
from pathlib import Path

from warpline.envelope import ENRICHMENT_VOCAB

FIXTURES = Path("tests/fixtures/contracts/warpline")

ENVELOPE_KEYS = {"schema", "ok", "query", "data", "warnings", "next_actions", "enrichment", "meta"}


def load(name: str) -> dict[str, object]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _assert_frozen_envelope(fixture: dict[str, object]) -> None:
    assert ENVELOPE_KEYS <= set(fixture)
    assert fixture["ok"] is True
    enrichment = fixture["enrichment"]
    assert isinstance(enrichment, dict)
    # CLOSED enrichment vocabulary, all six keys present.
    assert set(enrichment) == set(ENRICHMENT_VOCAB)
    for key, value in enrichment.items():
        assert value in ENRICHMENT_VOCAB[key]
    meta = fixture["meta"]
    assert isinstance(meta, dict)
    assert meta["local_only"] is True
    assert meta["peer_side_effects"] == []


def test_mcp_tool_inventory_is_agent_first_and_enrich_only() -> None:
    fixture = load("mcp-tool-inventory.json")
    assert fixture["schema"] == "warpline.mcp_tool_inventory.v1"
    assert fixture["status"] == "admitted-frozen"
    tools = fixture["tools"]
    assert isinstance(tools, list)
    names = [tool["name"] for tool in tools if isinstance(tool, dict)]
    assert names == sorted(names)
    # endorsed names AND short shims both advertised
    assert {"changed", "timeline", "blast_radius", "reverify", "capture_snapshot", "churn"} <= set(
        names
    )
    assert {
        "warpline_change_list",
        "warpline_entity_timeline_get",
        "warpline_entity_churn_count_get",
        "warpline_impact_radius_get",
        "warpline_reverify_worklist_get",
        "warpline_edge_snapshot_capture",
    } <= set(names)
    for tool in tools:
        assert isinstance(tool, dict)
        is_capture = tool["name"] in {"capture_snapshot", "warpline_edge_snapshot_capture"}
        assert tool["mutates"] is is_capture
        assert tool["local_only"] is True
        assert tool["peer_side_effects"] == []
        assert isinstance(tool["read_only"], bool)
        assert tool["writes_local_state"] is True
        assert tool["idempotent"] is True
        assert tool["mutates_paths"] == [".weft/warpline/"]
        assert isinstance(tool["federation_dependencies"], list)
        assert tool["schema"].startswith("warpline.") and ".draft." not in tool["schema"]
        assert tool["authority_boundary"]


def test_changed_response_fixture_is_frozen_envelope() -> None:
    fixture = load("mcp-response-changed.json")
    assert fixture["schema"] == "warpline.change_list.v1"
    _assert_frozen_envelope(fixture)
    data = fixture["data"]
    assert isinstance(data, dict)
    item = data["items"][0]
    assert {"locator", "sei"} <= set(item["entity"])
    assert data["changed_refs"][0]["kind"] == "sei"
    next_actions = fixture["next_actions"]
    assert isinstance(next_actions, dict)
    assert "warpline_reverify_worklist_get" in next_actions


def test_reverify_response_fixture_carries_honesty_fields() -> None:
    fixture = load("mcp-response-reverify.json")
    assert fixture["schema"] == "warpline.reverify_worklist.v1"
    _assert_frozen_envelope(fixture)
    data = fixture["data"]
    assert isinstance(data, dict)
    assert data["completeness"] in {"FULL", "DELTA", "NO_SNAPSHOT", "SKIPPED"}
    assert "staleness" in data
    assert "items" in data
    # PDR-0023: the resolve join is interrogable — every changed ref lands in
    # exactly one of resolved/unresolved, never silently dropped.
    assert isinstance(data["resolved"], list)
    assert isinstance(data["unresolved"], list)
    assert data["next_actions"] == {"filigree": []}
