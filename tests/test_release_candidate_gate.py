from __future__ import annotations

from pathlib import Path


def test_release_candidate_script_runs_required_gates() -> None:
    script = Path("scripts/check_release_candidate.sh")
    assert script.exists()
    text = script.read_text(encoding="utf-8")
    required = [
        "heddle productization-gate",
        "ruff check",
        "mypy src/heddle",
        "pytest tests",
        "check_no_member_diffs.sh",
        "run_spike.sh",
        "heddle dogfood-eval",
    ]
    for item in required:
        assert item in text
    assert text.index("run_spike.sh") < text.index("heddle productization-gate")
    assert text.index("heddle dogfood-eval") < text.index("heddle productization-gate")
    assert text.count("git diff --quiet") >= 2
