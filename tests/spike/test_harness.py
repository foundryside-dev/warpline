from __future__ import annotations

from pathlib import Path

from heddle.reverify import render_reverify_worklist


def test_spike_report_has_recommendation_line() -> None:
    report = Path("spike/REPORT.md")
    assert report.exists()
    text = report.read_text(encoding="utf-8")
    assert "Recommendation:" in text
    assert any(word in text for word in ["go", "no-go", "park-until-cutover"])


def test_spike_measurements_cover_required_nfrs() -> None:
    measurements = Path("spike/measurements.json")
    assert measurements.exists()
    text = measurements.read_text(encoding="utf-8")
    for key in (
        "changed_latency_ms",
        "backfill_events_per_second",
        "hook_ingest_exit_code",
        "planted_recall",
        "snapshot_completeness",
    ):
        assert key in text


def test_spike_harness_does_not_backfill_live_member_repos() -> None:
    script = Path("scripts/run_spike.sh").read_text(encoding="utf-8")
    for repo in (
        "/home/john/filigree",
        "/home/john/wardline",
        "/home/john/legis",
    ):
        assert repo not in script
    assert "heddle backfill --repo \"$repo\"" not in script


def test_reverify_worklist_carries_honesty_fields() -> None:
    items, work_seen, candidates = render_reverify_worklist(
        changed=[],
        affected=[],
        staleness={"snapshot_commit": None, "commits_behind": None},
        completeness="NO_SNAPSHOT",
    )
    assert items == []
    assert work_seen is False
    assert candidates == []
