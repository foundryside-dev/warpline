from __future__ import annotations

from pathlib import Path

from heddle.productization import ProductizationDecision, read_productization_decision


def write_dogfood_results(
    path: Path,
    *,
    solo: int,
    federation: int,
) -> None:
    path.write_text(
        (
            "{"
            '"schema":"heddle.dogfood_results.v1",'
            '"ready":true,'
            '"thresholds":{"solo_parity":8,"federation_uplift":8},'
            f'"summary":{{"solo":{{"parity":{solo}}},'
            f'"federation":{{"uplift":{federation}}}}},'
            '"cases":[]'
            "}\n"
        ),
        encoding="utf-8",
    )


def test_productization_gate_blocks_without_report(tmp_path: Path) -> None:
    decision = read_productization_decision(tmp_path / "missing.md")
    assert decision == ProductizationDecision(
        allowed=False,
        recommendation="missing",
        reason="spike report not found",
    )


def test_productization_gate_blocks_go_recommendation_without_dogfood(
    tmp_path: Path,
) -> None:
    report = tmp_path / "REPORT.md"
    report.write_text(
        "# Heddle Spike Report\n\nRecommendation: go\n\nOwner admission: pending\n",
        encoding="utf-8",
    )
    decision = read_productization_decision(
        report,
        dogfood_results_path=tmp_path / "missing-dogfood.json",
    )
    assert decision.allowed is False
    assert decision.recommendation == "dogfood-missing"


def test_productization_gate_allows_go_with_passing_dogfood(tmp_path: Path) -> None:
    report = tmp_path / "REPORT.md"
    report.write_text(
        "# Heddle Spike Report\n\nRecommendation: go\n\nOwner admission: pending\n",
        encoding="utf-8",
    )
    dogfood = tmp_path / "dogfood.json"
    write_dogfood_results(dogfood, solo=8, federation=8)
    decision = read_productization_decision(report, dogfood_results_path=dogfood)
    assert decision.allowed is True
    assert decision.recommendation == "go"


def test_productization_gate_blocks_go_with_failing_dogfood(tmp_path: Path) -> None:
    report = tmp_path / "REPORT.md"
    report.write_text(
        "# Heddle Spike Report\n\nRecommendation: go\n\nOwner admission: pending\n",
        encoding="utf-8",
    )
    dogfood = tmp_path / "dogfood.json"
    write_dogfood_results(dogfood, solo=8, federation=7)
    decision = read_productization_decision(report, dogfood_results_path=dogfood)
    assert decision.allowed is False
    assert decision.recommendation == "dogfood-failed"


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
