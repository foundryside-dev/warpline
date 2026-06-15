"""Rung 2 Track A: temporal co-change coupling graph (schema v3).

Locks the behaviours the plan names: canonical pair derivation, the closed
confidence vocab and its thresholds, sample-floor rate suppression, the R8/M7
per-commit >30 fan-out cap (recorded to health_log AND returned), the B4
``WARPLINE_COCHANGE`` kill-switch, fail-soft writes, ``rebuild-coupling``
idempotence, and the honest ``sei:null`` / ``enrichment.sei:absent`` surface for
SEI-sparse partners. The graph keys on warpline-local ``entity_key_id`` only and
joins the SEI at read time — never minting one.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import git as _git
from conftest import init_repo as _init_repo

from warpline.coupling import (
    classify_confidence,
    coupling_rate,
    derive_pairs_from_commit,
)
from warpline.git import backfill, ingest_commit
from warpline.store import WarplineStore, default_store_path

# --- pure derivation helpers -------------------------------------------------


def test_derive_pairs_canonical_ordering_and_dedup() -> None:
    # Unsorted, with a duplicate id — pairs come out sorted, canonical (a<b),
    # and the duplicate collapses.
    pairs = derive_pairs_from_commit([3, 1, 2, 1])
    assert pairs == [(1, 2), (1, 3), (2, 3)]
    for a, b in pairs:
        assert a < b


def test_derive_pairs_singleton_and_empty_yield_no_pairs() -> None:
    assert derive_pairs_from_commit([]) == []
    assert derive_pairs_from_commit([7]) == []


def test_classify_confidence_thresholds() -> None:
    assert classify_confidence(0) == "low"
    assert classify_confidence(4) == "low"
    assert classify_confidence(5) == "medium"
    assert classify_confidence(19) == "medium"
    assert classify_confidence(20) == "high"
    assert classify_confidence(99) == "high"


def test_coupling_rate_suppressed_below_sample_floor() -> None:
    # total < 5 → None (the rate is not yet meaningful).
    assert coupling_rate(2, 4) is None
    assert coupling_rate(0, 0) is None
    # total >= 5 → real fraction, clamped to [0, 1].
    assert coupling_rate(3, 6) == pytest.approx(0.5)
    assert coupling_rate(10, 5) == 1.0  # clamped, never > 1


# --- store: update_co_change_pairs -------------------------------------------


def test_update_co_change_pairs_counts_and_upserts(tmp_path: Path) -> None:
    db = tmp_path / "warpline.db"
    with WarplineStore.open(db) as store:
        repo_id = store.ensure_repo(tmp_path)
        r1 = store.update_co_change_pairs(repo_id, "sha1", {1, 2, 3}, changed_at="2024-01-01")
        assert r1 == {"pairs": 3}
        # Re-changing the same pair bumps its count.
        r2 = store.update_co_change_pairs(repo_id, "sha2", {1, 2}, changed_at="2024-01-02")
        assert r2 == {"pairs": 1}
        row = store.conn.execute(
            "SELECT co_change_count, last_commit_sha, last_co_change FROM co_change_pairs "
            "WHERE entity_key_id_a=1 AND entity_key_id_b=2"
        ).fetchone()
        assert row["co_change_count"] == 2
        assert row["last_commit_sha"] == "sha2"
        assert row["last_co_change"] == "2024-01-02"


def test_update_co_change_pairs_singleton_writes_nothing(tmp_path: Path) -> None:
    db = tmp_path / "warpline.db"
    with WarplineStore.open(db) as store:
        repo_id = store.ensure_repo(tmp_path)
        assert store.update_co_change_pairs(repo_id, "sha1", {7}) == {"pairs": 0}
        n = store.conn.execute("SELECT COUNT(*) AS c FROM co_change_pairs").fetchone()["c"]
        assert n == 0


def test_high_fanout_commit_is_skipped_and_recorded(tmp_path: Path) -> None:
    """R8/M7: >30 entities in one commit → skip, record to health_log AND return."""
    db = tmp_path / "warpline.db"
    with WarplineStore.open(db) as store:
        repo_id = store.ensure_repo(tmp_path)
        big = set(range(1, 35))  # 34 entities > cap 30
        report = store.update_co_change_pairs(repo_id, "fanout", big)
        assert report == {"pairs": 0, "skipped": "high_fanout", "entities": 34}
        # Nothing written.
        n = store.conn.execute("SELECT COUNT(*) AS c FROM co_change_pairs").fetchone()["c"]
        assert n == 0
        # Health event recorded.
        codes = [
            r["code"]
            for r in store.conn.execute("SELECT code FROM health_log ORDER BY id").fetchall()
        ]
        assert "coupling_skipped" in codes


def test_kill_switch_skips_all_writes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """B4: WARPLINE_COCHANGE=0 → skip + return, zero co_change_pairs rows."""
    monkeypatch.setenv("WARPLINE_COCHANGE", "0")
    db = tmp_path / "warpline.db"
    with WarplineStore.open(db) as store:
        repo_id = store.ensure_repo(tmp_path)
        report = store.update_co_change_pairs(repo_id, "sha1", {1, 2, 3})
        assert report == {"pairs": 0, "skipped": "kill_switch"}
        n = store.conn.execute("SELECT COUNT(*) AS c FROM co_change_pairs").fetchone()["c"]
        assert n == 0


def test_kill_switch_via_ingest_yields_zero_rows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """B4 end-to-end: an ingest under WARPLINE_COCHANGE=0 records no pairs."""
    monkeypatch.setenv("WARPLINE_COCHANGE", "false")
    repo = _init_repo(tmp_path)
    (repo / "a.py").write_text("x = 1\n", encoding="utf-8")
    (repo / "b.py").write_text("y = 2\n", encoding="utf-8")
    _git(repo, "add", "a.py", "b.py")
    _git(repo, "commit", "-m", "two files")
    with WarplineStore.open(default_store_path(repo)) as store:
        ingest_commit(store, repo, "HEAD")
        n = store.conn.execute("SELECT COUNT(*) AS c FROM co_change_pairs").fetchone()["c"]
    assert n == 0


def test_co_change_write_is_fail_soft(tmp_path: Path) -> None:
    """A SQLite write error is recorded and swallowed — never blocks ingest.

    Drop ``co_change_pairs`` out from under the writer so the INSERT raises
    ``OperationalError`` (the fail-soft branch); ``health_log`` still exists so
    the skip is recorded rather than propagated.
    """
    db = tmp_path / "warpline.db"
    with WarplineStore.open(db) as store:
        repo_id = store.ensure_repo(tmp_path)
        store.conn.execute("DROP TABLE co_change_pairs")
        store.conn.commit()
        report = store.update_co_change_pairs(repo_id, "sha1", {1, 2})
        assert report["pairs"] == 0
        assert "error" in report
        codes = [
            r["code"]
            for r in store.conn.execute("SELECT code FROM health_log ORDER BY id").fetchall()
        ]
        assert "coupling_write_failed" in codes


# --- ingest + read surface ---------------------------------------------------


def _two_coupled_files(tmp_path: Path) -> Path:
    repo = _init_repo(tmp_path)
    (repo / "a.py").write_text("x = 1\n", encoding="utf-8")
    (repo / "b.py").write_text("y = 1\n", encoding="utf-8")
    _git(repo, "add", "a.py", "b.py")
    _git(repo, "commit", "-m", "c1")
    return repo


def test_ingest_records_co_change_partners(tmp_path: Path) -> None:
    repo = _two_coupled_files(tmp_path)
    with WarplineStore.open(default_store_path(repo)) as store:
        ingest_commit(store, repo, "HEAD")
        a = store.resolve_ref(repo, "locator", "file:a.py")
        assert a is not None
        partners = store.co_change_partners(repo, int(a["id"]), min_count=1)
    locators = {str(p["locator"]) for p in partners}
    assert "file:b.py" in locators


def test_sei_sparse_partner_reads_null_sei(tmp_path: Path) -> None:
    """SEI-sparse pairs surface sei:null (no SEI minted; honest absence)."""
    repo = _two_coupled_files(tmp_path)
    with WarplineStore.open(default_store_path(repo)) as store:
        ingest_commit(store, repo, "HEAD")  # no sei_client → SEI stays NULL
        a = store.resolve_ref(repo, "locator", "file:a.py")
        assert a is not None
        partners = store.co_change_partners(repo, int(a["id"]), min_count=1)
    assert partners
    assert all(p["sei"] is None for p in partners)


def test_co_change_cli_payload_marks_sei_absent(tmp_path: Path) -> None:
    """The co-change read surface emits enrichment.sei == 'absent' for null SEI."""
    from warpline.cli import _co_change_payload

    repo = _two_coupled_files(tmp_path)
    with WarplineStore.open(default_store_path(repo)) as store:
        ingest_commit(store, repo, "HEAD")
    payload = _co_change_payload(
        repo, sei=None, locator="file:a.py", entity_key_id=None, min_count=1
    )
    partners = payload["partners"]
    assert isinstance(partners, list) and partners
    for partner in partners:
        assert partner["sei"] is None
        assert partner["enrichment"]["sei"] == "absent"
        assert partner["confidence"] in {"low", "medium", "high"}


def test_co_change_cli_payload_requires_a_selector(tmp_path: Path) -> None:
    from warpline.cli import _co_change_payload

    repo = _init_repo(tmp_path)
    with WarplineStore.open(default_store_path(repo)):
        pass
    payload = _co_change_payload(
        repo, sei=None, locator=None, entity_key_id=None, min_count=2
    )
    assert payload["partners"] == []
    assert "error" in payload


# --- rebuild -----------------------------------------------------------------


def test_rebuild_coupling_is_idempotent(tmp_path: Path) -> None:
    """rebuild-coupling run twice → identical counts (idempotent)."""
    repo = _two_coupled_files(tmp_path)
    (repo / "a.py").write_text("x = 2\n", encoding="utf-8")
    (repo / "b.py").write_text("y = 2\n", encoding="utf-8")
    _git(repo, "add", "a.py", "b.py")
    _git(repo, "commit", "-m", "c2")

    with WarplineStore.open(default_store_path(repo)) as store:
        backfill(store, repo)

        def _counts() -> list[tuple[int, int, int]]:
            return [
                (int(r["entity_key_id_a"]), int(r["entity_key_id_b"]), int(r["co_change_count"]))
                for r in store.conn.execute(
                    "SELECT entity_key_id_a, entity_key_id_b, co_change_count "
                    "FROM co_change_pairs ORDER BY entity_key_id_a, entity_key_id_b"
                ).fetchall()
            ]

        first = store.rebuild_co_change_pairs(repo)
        counts_1 = _counts()
        second = store.rebuild_co_change_pairs(repo)
        counts_2 = _counts()

    assert first == second
    assert counts_1 == counts_2
    # a.py and b.py changed together in both commits → count 2.
    assert counts_1
    assert any(c == 2 for *_pair, c in counts_1)


def test_rebuild_matches_incremental_ingest(tmp_path: Path) -> None:
    """A rebuild converges to the same counts the live ingest path produced."""
    repo = _two_coupled_files(tmp_path)
    with WarplineStore.open(default_store_path(repo)) as store:
        ingest_commit(store, repo, "HEAD")
        live = [
            (int(r["entity_key_id_a"]), int(r["entity_key_id_b"]), int(r["co_change_count"]))
            for r in store.conn.execute(
                "SELECT entity_key_id_a, entity_key_id_b, co_change_count "
                "FROM co_change_pairs ORDER BY entity_key_id_a, entity_key_id_b"
            ).fetchall()
        ]
        store.rebuild_co_change_pairs(repo)
        rebuilt = [
            (int(r["entity_key_id_a"]), int(r["entity_key_id_b"]), int(r["co_change_count"]))
            for r in store.conn.execute(
                "SELECT entity_key_id_a, entity_key_id_b, co_change_count "
                "FROM co_change_pairs ORDER BY entity_key_id_a, entity_key_id_b"
            ).fetchall()
        ]
    assert live == rebuilt
