from __future__ import annotations

from pathlib import Path

REQUIREMENTS = [
    "FR-01",
    "FR-02",
    "FR-03",
    "FR-04",
    "FR-05",
    "FR-06",
    "FR-07",
    "FR-08",
    "NFR-01",
    "NFR-02",
    "NFR-03",
    "NFR-04",
    "NFR-05",
    "NFR-06",
    "CON-TEC-01",
    "CON-TEC-02",
    "CON-TEC-03",
    "CON-ORG-01",
    "CON-ORG-02",
    "CON-ORG-03",
    "CON-ORG-04",
]


def test_delivery_plan_traces_every_requirement_to_task_and_verification() -> None:
    text = Path("docs/plans/2026-06-12-heddle-delivery.md").read_text(encoding="utf-8")
    missing: list[str] = []
    weak: list[str] = []
    for req in REQUIREMENTS:
        rows = [line for line in text.splitlines() if line.startswith(f"| {req} ")]
        if not rows:
            missing.append(req)
            continue
        row = rows[0]
        if "Task" not in row or not any(
            token in row for token in ("tests/", "scripts/", "pytest", "bash ")
        ):
            weak.append(req)
    assert missing == []
    assert weak == []
