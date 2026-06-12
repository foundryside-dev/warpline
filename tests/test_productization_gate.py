from __future__ import annotations

from pathlib import Path

from heddle.productization import ProductizationDecision, read_productization_decision


def test_productization_gate_blocks_without_report(tmp_path: Path) -> None:
    decision = read_productization_decision(tmp_path / "missing.md")
    assert decision == ProductizationDecision(
        allowed=False,
        recommendation="missing",
        reason="spike report not found",
    )


def test_productization_gate_allows_go_recommendation(tmp_path: Path) -> None:
    report = tmp_path / "REPORT.md"
    report.write_text(
        "# Heddle Spike Report\n\nRecommendation: go\n\nOwner admission: pending\n",
        encoding="utf-8",
    )
    decision = read_productization_decision(report)
    assert decision.allowed is True
    assert decision.recommendation == "go"


def test_productization_gate_blocks_no_go(tmp_path: Path) -> None:
    report = tmp_path / "REPORT.md"
    report.write_text("Recommendation: no-go\n", encoding="utf-8")
    decision = read_productization_decision(report)
    assert decision.allowed is False
    assert decision.recommendation == "no-go"


def test_productization_gate_blocks_not_ready_verdict_even_with_go(
    tmp_path: Path,
) -> None:
    report = tmp_path / "REPORT.md"
    report.write_text(
        "Readiness verdict: not-ready\n\nRecommendation: go\n",
        encoding="utf-8",
    )
    decision = read_productization_decision(report)
    assert decision.allowed is False
    assert decision.recommendation == "not-ready"
    assert decision.reason == "readiness verdict is not-ready"
