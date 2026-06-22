"""Characterization tests for the pure staleness/completeness helpers.

Locks the (completeness, staleness) -> enrichment.edges mapping and the
warning text BEFORE the Rung 0 extraction moves these bodies into
``warpline._enrichment``. Pure functions, no fixtures. These imports are
retargeted to ``warpline._enrichment`` in Step 0.2; until then they pin the
behaviour as it lives in ``warpline.commands``.
"""

from __future__ import annotations

from pathlib import Path

from warpline import commands
from warpline._enrichment import (
    EDGES_FOR_COMPLETENESS,
    completeness_warnings,
    edges_enrichment,
    is_stale,
    requirements_reason,
    sei_reason,
    staleness_warnings,
)
from warpline.store import WarplineStore, default_store_path


# --------------------------------------------------------------------------- is_stale
def test_is_stale_zero_commits_behind_is_fresh() -> None:
    assert is_stale({"commits_behind": 0, "snapshot_commit": "abc"}) is False


def test_is_stale_positive_commits_behind_is_stale() -> None:
    assert is_stale({"commits_behind": 3, "snapshot_commit": "abc"}) is True


def test_is_stale_none_behind_with_snapshot_is_stale() -> None:
    # Could not ask git, but a snapshot commit exists -> unknown therefore stale.
    assert is_stale({"commits_behind": None, "snapshot_commit": "abc"}) is True


def test_is_stale_none_behind_without_snapshot_is_fresh() -> None:
    # No snapshot commit at all -> nothing to be behind.
    assert is_stale({"commits_behind": None, "snapshot_commit": None}) is False


# --------------------------------------------------------------------------- EDGES map
def test_edges_for_completeness_constant() -> None:
    assert EDGES_FOR_COMPLETENESS == {
        "FULL": "present",
        "DELTA": "partial",
        "NO_SNAPSHOT": "absent",
        "SKIPPED": "skipped",
    }


# --------------------------------------------------------------------------- edges_enrichment
def test_edges_enrichment_full_fresh_is_present() -> None:
    fresh = {"commits_behind": 0, "snapshot_commit": "abc"}
    assert edges_enrichment("FULL", fresh) == "present"


def test_edges_enrichment_full_stale_downgrades_to_stale() -> None:
    stale = {"commits_behind": 2, "snapshot_commit": "abc"}
    assert edges_enrichment("FULL", stale) == "stale"


def test_edges_enrichment_delta_fresh_is_partial() -> None:
    fresh = {"commits_behind": 0, "snapshot_commit": "abc"}
    assert edges_enrichment("DELTA", fresh) == "partial"


def test_edges_enrichment_delta_stale_downgrades_to_stale() -> None:
    stale = {"commits_behind": 1, "snapshot_commit": "abc"}
    assert edges_enrichment("DELTA", stale) == "stale"


def test_edges_enrichment_no_snapshot_is_absent_regardless_of_staleness() -> None:
    stale = {"commits_behind": 5, "snapshot_commit": "abc"}
    assert edges_enrichment("NO_SNAPSHOT", stale) == "absent"


def test_edges_enrichment_skipped_is_skipped_regardless_of_staleness() -> None:
    stale = {"commits_behind": 5, "snapshot_commit": "abc"}
    assert edges_enrichment("SKIPPED", stale) == "skipped"


def test_edges_enrichment_unknown_completeness_defaults_to_absent() -> None:
    fresh = {"commits_behind": 0, "snapshot_commit": "abc"}
    assert edges_enrichment("WEIRD", fresh) == "absent"


# --------------------------------------------------------------------------- staleness_warnings
def test_staleness_warnings_full_fresh_is_empty() -> None:
    fresh = {"commits_behind": 0, "snapshot_commit": "abc"}
    assert staleness_warnings("FULL", fresh) == []


def test_staleness_warnings_full_stale_known_count() -> None:
    stale = {"commits_behind": 2, "snapshot_commit": "abcdef0123"}
    warns = staleness_warnings("FULL", stale)
    assert len(warns) == 1
    assert warns[0].startswith("STALE: edge snapshot @ abcdef01")
    assert "2 commit(s) behind HEAD" in warns[0]


def test_staleness_warnings_full_stale_unknown_count() -> None:
    stale = {"commits_behind": None, "snapshot_commit": "abcdef0123"}
    warns = staleness_warnings("FULL", stale)
    assert len(warns) == 1
    assert "freshness unknown" in warns[0]


def test_staleness_warnings_no_snapshot_is_empty() -> None:
    stale = {"commits_behind": 5, "snapshot_commit": "abc"}
    assert staleness_warnings("NO_SNAPSHOT", stale) == []


# --------------------------------------------------------------------------- completeness_warnings
def test_completeness_warnings_no_snapshot() -> None:
    warns = completeness_warnings("NO_SNAPSHOT")
    assert warns == ["NO_SNAPSHOT: downstream traversal unavailable; changed set only"]


def test_completeness_warnings_skipped() -> None:
    warns = completeness_warnings("SKIPPED")
    assert warns == ["SKIPPED: graph snapshot was skipped; changed set only"]


def test_completeness_warnings_delta() -> None:
    warns = completeness_warnings("DELTA")
    assert warns == ["DELTA: graph snapshot is partial; inspect failed_entities or staleness"]


def test_completeness_warnings_full_is_empty() -> None:
    assert completeness_warnings("FULL") == []


# ----------------------------------------------------- capture_snapshot dict access (B1)
def test_capture_snapshot_maps_edges_via_edges_for_completeness(tmp_path: Path) -> None:
    """``capture_snapshot`` reads ``EDGES_FOR_COMPLETENESS`` (commands.py) to map
    its completeness to ``enrichment.edges``. This pins that dict access stays
    wired after the Rung 0 extraction: with no loomweave the capture is SKIPPED,
    so the closed vocab must resolve to ``"skipped"`` (not the absent fallback).
    """

    repo = tmp_path / "repo"
    repo.mkdir()
    with WarplineStore.open(default_store_path(repo)) as store:
        store.ensure_repo(repo)
    envelope = commands.capture_snapshot(
        repo, commit="c1", loomweave_command="/no/such/loomweave"
    )
    assert envelope["data"]["completeness"] == "SKIPPED"
    assert envelope["enrichment"]["edges"] == EDGES_FOR_COMPLETENESS["SKIPPED"] == "skipped"


# --------------------------------------------------------------------------- sei_reason
def test_sei_present_is_clean() -> None:
    assert sei_reason("present") == {"reason_class": "clean"}


def test_sei_absent_is_unresolved_input_with_cause_and_fix() -> None:
    triple = sei_reason("absent")
    assert triple is not None
    assert triple["reason_class"] == "unresolved_input"
    assert "resolv" in triple["cause"].lower()
    assert triple["fix"]


def test_sei_unavailable_is_unreachable_with_cause_and_fix() -> None:
    triple = sei_reason("unavailable")
    assert triple is not None
    assert triple["reason_class"] == "unreachable"
    assert "loomweave" in triple["cause"].lower()
    assert triple["fix"]


def test_sei_unknown_state_yields_no_triple() -> None:
    assert sei_reason("bogus") is None


def test_requirements_reason_is_stable_disabled() -> None:
    assert requirements_reason()["reason_class"] == "disabled"
