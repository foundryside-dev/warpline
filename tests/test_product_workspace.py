from __future__ import annotations

from pathlib import Path

PRODUCT_ROOT = Path("docs/product")


def read_product_doc(path: str) -> str:
    return (PRODUCT_ROOT / path).read_text(encoding="utf-8")


def test_product_workspace_has_required_ownership_artifacts() -> None:
    required = [
        "vision.md",
        "roadmap.md",
        "current-state.md",
        "metrics.md",
        "decisions/0001-product-candidate-ownership.md",
        "prds/PRD-0001-agent-first-mcp-productization.md",
        "agentic-mcp-product-design.md",
    ]
    for path in required:
        assert (PRODUCT_ROOT / path).exists(), path


def test_vision_names_heddle_federation_authority_and_refusals() -> None:
    text = read_product_doc("vision.md")
    assert "Heddle owns temporal change-impact facts" in text
    assert "Loomweave owns current structure" in text
    assert "Heddle does not own work state, trust policy, governance, or obligations" in text
    assert "Escalate BEFORE acting" in text


def test_mcp_product_design_treats_agent_surface_as_primary() -> None:
    text = read_product_doc("agentic-mcp-product-design.md")
    assert "MCP deficiencies are P0 product defects" in text
    assert "Heddle has no reason to exist" in text
    assert "at least as good as existing tools" in text
    assert "better with federation members" in text
    assert "tools/list is the front door" in text
    assert "manual grep" in text
    assert "first-class Weft federation member" in text


def test_product_metrics_are_falsifiable_and_guard_federation_boundaries() -> None:
    text = read_product_doc("metrics.md")
    assert "Target (falsifiable)" in text
    assert "8 of 10 dogfood diffs" in text
    assert "solo parity" in text
    assert "federation uplift" in text
    assert "Member repo diff violations" in text
    assert "0" in text


def test_prd_contains_reject_branches_for_mcp_productization() -> None:
    text = read_product_doc("prds/PRD-0001-agent-first-mcp-productization.md")
    assert "Reject branch" in text
    assert "If an agent must inspect raw SQLite or manually grep" in text
    assert "ready-for-planning" in text
