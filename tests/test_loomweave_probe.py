from __future__ import annotations

from pathlib import Path

from heddle.loomweave import LoomweaveProbe


def test_missing_loomweave_degrades_cleanly(tmp_path: Path) -> None:
    probe = LoomweaveProbe(repo=tmp_path, command="/no/such/loomweave")
    result = probe.probe()
    assert result["status"] == "skipped"
    assert result["reason"] == "command_unavailable"


def test_probe_reports_expected_read_tools(tmp_path: Path) -> None:
    probe = LoomweaveProbe(repo=tmp_path)
    assert {"entity_find", "entity_resolve", "entity_callers_list"} <= probe.expected_tools()
