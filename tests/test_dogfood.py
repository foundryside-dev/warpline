from __future__ import annotations

import json
from pathlib import Path

from heddle import cli
from heddle.dogfood import run_dogfood_evaluator


def test_dogfood_evaluator_writes_required_machine_readable_contract(
    tmp_path: Path,
) -> None:
    output = tmp_path / "dogfood.json"
    result = run_dogfood_evaluator(output_path=output, work_dir=tmp_path / "work")

    assert output.exists()
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload == result
    assert payload["schema"] == "heddle.dogfood_results.v1"
    assert payload["thresholds"] == {"solo_parity": 8, "federation_uplift": 8}
    assert payload["summary"]["solo"]["parity"] >= 8
    assert payload["summary"]["federation"]["uplift"] >= 8
    assert payload["ready"] is True
    assert len(payload["cases"]) == 20
    for case in payload["cases"]:
        assert {
            "case_id",
            "lane",
            "tool_calls",
            "baseline_answer",
            "heddle_answer",
            "parity",
            "uplift",
            "failure_reason",
            "manual_escape_required",
            "enrichment_state",
        } <= set(case)
        assert case["tool_calls"] <= 2
        assert case["manual_escape_required"] is False


def test_cli_dogfood_eval_writes_output(tmp_path: Path) -> None:
    output = tmp_path / "dogfood.json"
    assert (
        cli.main(
            [
                "dogfood-eval",
                "--output",
                str(output),
                "--work-dir",
                str(tmp_path / "work"),
                "--json",
            ]
        )
        == 0
    )
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["ready"] is True
