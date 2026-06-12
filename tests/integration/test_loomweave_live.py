from __future__ import annotations

from pathlib import Path

import pytest

from heddle.loomweave import LoomweaveProbe


def test_live_loomweave_probe_reports_surface() -> None:
    repo = Path("/home/john/loomweave")
    result = LoomweaveProbe(repo=repo).probe()
    if result["status"] == "skipped":
        pytest.skip(f"loomweave unavailable for live probe: {result}")
    assert "entity_neighborhood_get" in result["tools"]
