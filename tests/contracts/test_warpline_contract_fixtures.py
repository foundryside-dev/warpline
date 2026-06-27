from __future__ import annotations

import json
from pathlib import Path

from warpline.envelope import ENRICHMENT_VOCAB
from warpline.listing import REASON_CLASSES

FIXTURES = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "contracts" / "warpline"

ENVELOPE_KEYS = {
    "schema",
    "ok",
    "query",
    "data",
    "warnings",
    "next_actions",
    "enrichment",
    "enrichment_reasons",
    "meta",
}


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
    # enrichment_reasons mirrors build_envelope's contract (envelope.py:78-94):
    # every dimension is in the closed vocab and every value is a listing.reason()
    # triple (a canonical reason_class; non-clean carries both cause and fix). The
    # reserved-but-honest `requirements` triple rides on EVERY frozen envelope and
    # is universally `disabled` (no transport wired) — never a bare unexplained scalar.
    reasons = fixture["enrichment_reasons"]
    assert isinstance(reasons, dict)
    assert "requirements" in reasons
    assert reasons["requirements"]["reason_class"] == "disabled"
    for dim, carrier in reasons.items():
        assert dim in ENRICHMENT_VOCAB
        assert isinstance(carrier, dict)
        assert carrier.get("reason_class") in REASON_CLASSES
        if carrier["reason_class"] != "clean":
            assert carrier.get("cause") and carrier.get("fix")
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
        is_mutating = tool["name"] in {
            "capture_snapshot", "warpline_edge_snapshot_capture",
            "verify_record", "warpline_verification_record",
        }
        assert tool["mutates"] is is_mutating
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
    # FROZEN raw snapshot-completeness STRING (unchanged on v1).
    assert data["completeness"] in {"FULL", "DELTA", "NO_SNAPSHOT", "SKIPPED"}
    # Federation D1 (additive v1): the derived impact-completeness OBJECT wardline
    # mirrors verbatim into producer_completeness, plus the producer timestamp.
    impact = data["impact_completeness"]
    assert isinstance(impact, dict)
    assert set(impact) == {
        "status",
        "as_of",
        "graph_fresh",
        "graph_ref",
        "depth_capped",
        "unresolved_count",
        "reasons",
    }
    assert impact["status"] in {"complete", "partial", "unknown"}
    assert isinstance(impact["as_of"], str)
    assert isinstance(impact["graph_fresh"], bool)
    assert isinstance(impact["depth_capped"], bool)
    assert isinstance(impact["unresolved_count"], int)
    assert isinstance(impact["reasons"], list)
    # The producer timestamp (staleness axis) lives inside impact_completeness; the
    # redundant top-level data.generated_at was removed (federation reads one object).
    assert "generated_at" not in data
    # Rung-2 risk-as-verification posture is always emitted (here: no bundle ->
    # the completeness gate leaves it unavailable, never a warpline clean).
    rv = data["risk_verification"]
    assert isinstance(rv, dict)
    assert rv["risk"] in {"proven", "unavailable"}
    assert isinstance(rv["reason_code"], str)
    assert rv["reason"]["reason_class"] != "clean" or rv["risk"] == "proven"
    assert "staleness" in data
    assert "items" in data
    # PDR-0023: the resolve join is interrogable — every changed ref lands in
    # exactly one of resolved/unresolved, never silently dropped.
    assert isinstance(data["resolved"], list)
    assert isinstance(data["unresolved"], list)
    assert data["next_actions"] == {"filigree": []}


def test_fixtures_root_resolves_independent_of_cwd(tmp_path: Path, monkeypatch) -> None:
    """The fixture root must resolve from the test file location, not the process cwd, so the
    federation hub can run this suite from any working directory (portability)."""
    monkeypatch.chdir(tmp_path)
    assert (FIXTURES / "golden-vectors.json").is_file()
    assert (FIXTURES / "mcp-tool-inventory.json").is_file()
