"""Rung 1a: ordered migration runner + PRAGMA hardening.

The base SCHEMA is FROZEN after Rung 1a; all schema change lands via the ordered
``MIGRATIONS`` list. As of Rung 1b the real list carries v2 (anchor columns), so
the highest known version is 2. The runner mechanics (ordering, atomicity,
idempotence, concurrency safety) are still exercised against synthetic
migrations monkeypatched onto the module so they stay decoupled from any single
shipped version.
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

import pytest

from warpline import store as store_mod
from warpline.store import SCHEMA, Migration, WarplineStore


def _user_version(db: Path) -> int:
    conn = sqlite3.connect(db)
    try:
        return int(conn.execute("PRAGMA user_version").fetchone()[0])
    finally:
        conn.close()


def _health_codes(db: Path) -> list[str]:
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("SELECT code FROM health_log ORDER BY id").fetchall()
        return [str(r["code"]) for r in rows]
    finally:
        conn.close()


def test_fresh_db_lands_at_highest_known_version(tmp_path: Path) -> None:
    db = tmp_path / "warpline.db"
    with WarplineStore.open(db) as store:
        assert store.schema_version() == store_mod.HIGHEST_KNOWN_VERSION
    # As of Rung 1b the highest known version is 2 (anchor columns).
    assert _user_version(db) == store_mod.HIGHEST_KNOWN_VERSION
    assert store_mod.HIGHEST_KNOWN_VERSION == 2


def test_connection_pragmas_are_hardened(tmp_path: Path) -> None:
    db = tmp_path / "warpline.db"
    with WarplineStore.open(db) as store:
        assert int(store.conn.execute("PRAGMA foreign_keys").fetchone()[0]) == 1
        assert int(store.conn.execute("PRAGMA busy_timeout").fetchone()[0]) == 5000
        # journal_mode=WAL set via SCHEMA executescript (fresh-DB note).
        assert str(store.conn.execute("PRAGMA journal_mode").fetchone()[0]).lower() == "wal"


def test_legacy_v1_db_reconciles_then_upgrades_on_open(tmp_path: Path) -> None:
    """A pre-runner DB (base tables + meta='1', user_version=0) reconciles to 1
    then the real v2 anchor migration upgrades it to the highest known version."""
    db = tmp_path / "warpline.db"
    # Simulate a DB written before the runner existed: SCHEMA applied (so
    # meta.schema_version='1') but user_version never set.
    raw = sqlite3.connect(db)
    raw.executescript(SCHEMA)
    raw.commit()
    raw.close()
    assert _user_version(db) == 0

    with WarplineStore.open(db) as store:
        assert store.schema_version() == store_mod.HIGHEST_KNOWN_VERSION
        # The v2 anchor columns are present after the upgrade.
        cols = {r["name"] for r in store.conn.execute("PRAGMA table_info(change_events)")}
        assert {
            "detected_branch",
            "detected_head_sha",
            "detected_at",
            "detected_context",
        } <= cols
    assert _user_version(db) == store_mod.HIGHEST_KNOWN_VERSION
    # No reconcile-warn rows for the expected legacy baseline.
    assert "MIGRATION_META_RECONCILE" not in _health_codes(db)


def test_reopen_is_a_no_op(tmp_path: Path) -> None:
    db = tmp_path / "warpline.db"
    with WarplineStore.open(db) as store:
        assert store.schema_version() == store_mod.HIGHEST_KNOWN_VERSION
    first = _health_codes(db)
    with WarplineStore.open(db) as store:
        assert store.schema_version() == store_mod.HIGHEST_KNOWN_VERSION
    # Re-open adds no health rows and does not change the version.
    assert _health_codes(db) == first
    assert _user_version(db) == store_mod.HIGHEST_KNOWN_VERSION


def test_user_version_ahead_of_known_warns_to_health_log_and_does_not_fail(
    tmp_path: Path,
) -> None:
    """A DB written by a newer build (user_version > highest known) reads safely."""
    db = tmp_path / "warpline.db"
    with WarplineStore.open(db):
        pass
    # Forge a future on-disk version.
    raw = sqlite3.connect(db)
    raw.execute("PRAGMA user_version = 99")
    raw.commit()
    raw.close()

    with WarplineStore.open(db) as store:
        # schema_version() reads meta (still the highest known); runner did not fail.
        assert store.schema_version() == store_mod.HIGHEST_KNOWN_VERSION
        # Reads remain available.
        store.ensure_repo(tmp_path)
    assert _user_version(db) == 99  # untouched
    assert "SCHEMA_VERSION_AHEAD" in _health_codes(db)


def test_user_version_zero_with_divergent_meta_adopts_and_warns(tmp_path: Path) -> None:
    """M9: user_version==0 but meta.schema_version!='1' → adopt meta value + warn."""
    db = tmp_path / "warpline.db"
    raw = sqlite3.connect(db)
    raw.executescript(SCHEMA)
    raw.execute("UPDATE meta SET value = '5' WHERE key = 'schema_version'")
    raw.execute("PRAGMA user_version = 0")
    raw.commit()
    raw.close()

    with WarplineStore.open(db) as store:
        # Adopted 5 from meta; 5 > highest known (2), so it is also flagged ahead.
        assert store.schema_version() == 5
    codes = _health_codes(db)
    assert "MIGRATION_META_RECONCILE" in codes
    assert "SCHEMA_VERSION_AHEAD" in codes
    assert _user_version(db) == 5


def test_migration_runner_applies_ordered_steps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The runner applies steps version>current in order, updating both markers."""
    applied: list[int] = []

    def _v2(conn: sqlite3.Connection) -> None:
        conn.execute("CREATE TABLE rung1a_probe_v2 (x INTEGER)")
        applied.append(2)

    def _v3(conn: sqlite3.Connection) -> None:
        conn.execute("ALTER TABLE rung1a_probe_v2 ADD COLUMN y INTEGER")
        applied.append(3)

    migrations = [Migration(2, _v2), Migration(3, _v3)]
    monkeypatch.setattr(store_mod, "MIGRATIONS", migrations)
    monkeypatch.setattr(store_mod, "HIGHEST_KNOWN_VERSION", 3)

    db = tmp_path / "warpline.db"
    with WarplineStore.open(db) as store:
        assert store.schema_version() == 3
        cols = {r["name"] for r in store.conn.execute("PRAGMA table_info(rung1a_probe_v2)")}
        assert cols == {"x", "y"}
    assert applied == [2, 3]
    assert _user_version(db) == 3

    # Idempotent: re-open applies nothing further.
    applied.clear()
    with WarplineStore.open(db) as store:
        assert store.schema_version() == 3
    assert applied == []


def test_failed_migration_rolls_back_atomically(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R3: a raising step rolls back; user_version and meta stay at the prior version."""

    def _v2_boom(conn: sqlite3.Connection) -> None:
        conn.execute("CREATE TABLE rung1a_partial (x INTEGER)")
        raise RuntimeError("boom")

    monkeypatch.setattr(store_mod, "MIGRATIONS", [Migration(2, _v2_boom)])
    monkeypatch.setattr(store_mod, "HIGHEST_KNOWN_VERSION", 2)

    db = tmp_path / "warpline.db"
    with pytest.raises(RuntimeError, match="boom"):
        WarplineStore.open(db)

    # The partial table must NOT have been committed, and version stays at 1.
    assert _user_version(db) == 1
    conn = sqlite3.connect(db)
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='rung1a_partial'"
        ).fetchall()
        assert rows == []
    finally:
        conn.close()


def test_concurrent_open_does_not_double_apply(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two threads opening at once both converge to the migrated version once."""
    apply_count = 0
    lock = threading.Lock()

    def _v3(conn: sqlite3.Connection) -> None:
        nonlocal apply_count
        with lock:
            apply_count += 1
        conn.execute("CREATE TABLE IF NOT EXISTS rung1a_concurrent (x INTEGER)")

    db = tmp_path / "warpline.db"
    # Materialize the real base schema (lands at the highest known version) WITHOUT
    # the synthetic step in play, so both threads then race a single step above
    # that baseline from an identical starting version.
    with WarplineStore.open(db) as store:
        assert store.schema_version() == store_mod.HIGHEST_KNOWN_VERSION

    synthetic_version = store_mod.HIGHEST_KNOWN_VERSION + 1
    monkeypatch.setattr(
        store_mod, "MIGRATIONS", [Migration(synthetic_version, _v3)]
    )
    monkeypatch.setattr(store_mod, "HIGHEST_KNOWN_VERSION", synthetic_version)

    errors: list[BaseException] = []

    def _worker() -> None:
        try:
            with WarplineStore.open(db) as store:
                assert store.schema_version() == synthetic_version
        except BaseException as exc:  # noqa: BLE001 - surfaced via errors list
            errors.append(exc)

    threads = [threading.Thread(target=_worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    assert _user_version(db) == synthetic_version
    # The migration body ran exactly once across both opens.
    assert apply_count == 1
