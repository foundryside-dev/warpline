from __future__ import annotations

import sqlite3
from pathlib import Path

from warpline.store import HIGHEST_KNOWN_VERSION, WarplineStore, default_store_path


def _open(tmp_path: Path) -> WarplineStore:
    return WarplineStore.open(default_store_path(tmp_path))


def test_schema_reaches_version_4(tmp_path: Path) -> None:
    with _open(tmp_path) as store:
        version = store.conn.execute("PRAGMA user_version").fetchone()[0]
        assert int(version) == 4
        assert HIGHEST_KNOWN_VERSION == 4


def test_verification_events_table_exists(tmp_path: Path) -> None:
    with _open(tmp_path) as store:
        row = store.conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='verification_events'"
        ).fetchone()
        assert row is not None


def test_reopen_is_idempotent(tmp_path: Path) -> None:
    path = default_store_path(tmp_path)
    with WarplineStore.open(path) as store:
        store.conn.execute("PRAGMA user_version").fetchone()
    # Re-open: no migration re-runs, no error, still v4.
    with WarplineStore.open(path) as store:
        assert int(store.conn.execute("PRAGMA user_version").fetchone()[0]) == 4


def test_presence_floor_recovers_dropped_table(tmp_path: Path) -> None:
    """#9: a v4 marker claiming the schema but missing verification_events floors
    to v3 and re-runs the v4 migration via the user_version==0 reconcile path.

    This exercises the SAME presence-floor recovery the runner already guards for
    v3 (see test_inflated_meta_without_schema_objects_reruns_migrations): forge a
    DB whose meta marker CLAIMS v4 but whose verification_events table is gone,
    with user_version=0 so the reconcile path runs. The v2 anchor columns and v3
    co_change_pairs table are left intact, so the floor lands at exactly 3 and
    only the v4 migration re-runs.
    """

    path = default_store_path(tmp_path)
    # Materialize the full v4 schema, then forge the dropped-table scenario.
    with WarplineStore.open(path) as store:
        assert store.schema_version() == 4
    raw = sqlite3.connect(path)
    raw.row_factory = sqlite3.Row
    raw.execute("DROP TABLE verification_events")
    # Claim v4 in meta but reset user_version to 0 so the reconcile path runs.
    raw.execute("UPDATE meta SET value = '4' WHERE key = 'schema_version'")
    raw.execute("PRAGMA user_version = 0")
    raw.commit()
    # v2/v3 objects must remain intact so only v4 re-runs (not v2/v3).
    cols_before = {r["name"] for r in raw.execute("PRAGMA table_info(change_events)")}
    assert {"detected_branch", "detected_context"} <= cols_before
    tables_before = {
        str(r[0])
        for r in raw.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert "co_change_pairs" in tables_before
    assert "verification_events" not in tables_before
    raw.close()

    # Re-open: presence-floor floors to v3 and re-runs v4.
    with WarplineStore.open(path) as store:
        assert store.schema_version() == 4
        row = store.conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='verification_events'"
        ).fetchone()
        assert row is not None
        # v2/v3 objects were NOT collaterally dropped or rebuilt-from-empty in a way
        # that loses data: co_change_pairs still exists and anchor columns persist.
        assert store.conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='co_change_pairs'"
        ).fetchone() is not None
        cols_after = {r["name"] for r in store.conn.execute("PRAGMA table_info(change_events)")}
        assert {"detected_branch", "detected_context"} <= cols_after


def test_record_and_list_round_trip(tmp_path: Path) -> None:
    with _open(tmp_path) as store:
        repo_id = store.ensure_repo(tmp_path)
        store.record_verification_event(
            repo_id=repo_id,
            commit_sha="a" * 40,
            kind="test_pass",
            verified_at="2026-06-25T10:00:00+00:00",
            actor="ci-bot",
            source="warpline",
        )
        events = store.list_verification_events(tmp_path)
        assert len(events) == 1
        assert events[0]["commit_sha"] == "a" * 40
        assert events[0]["kind"] == "test_pass"
        assert events[0]["actor"] == "ci-bot"
        assert events[0]["source"] == "warpline"


def test_record_is_idempotent_on_unique_key(tmp_path: Path) -> None:
    with _open(tmp_path) as store:
        repo_id = store.ensure_repo(tmp_path)
        for _ in range(2):
            store.record_verification_event(
                repo_id=repo_id,
                commit_sha="b" * 40,
                kind="test_pass",
                verified_at="2026-06-25T10:00:00+00:00",
                actor="ci-bot",
                source="warpline",
            )
        assert len(store.list_verification_events(tmp_path)) == 1


def test_list_orders_by_verified_at(tmp_path: Path) -> None:
    with _open(tmp_path) as store:
        repo_id = store.ensure_repo(tmp_path)
        store.record_verification_event(
            repo_id=repo_id, commit_sha="c" * 40, kind="test_pass",
            verified_at="2026-06-25T12:00:00+00:00", actor=None, source="warpline",
        )
        store.record_verification_event(
            repo_id=repo_id, commit_sha="d" * 40, kind="test_pass",
            verified_at="2026-06-25T09:00:00+00:00", actor=None, source="warpline",
        )
        events = store.list_verification_events(tmp_path)
        assert [e["commit_sha"] for e in events] == ["d" * 40, "c" * 40]


def test_list_orders_chronologically_across_offsets(tmp_path: Path) -> None:
    # A chronologically-LATER value with a non-UTC offset must NOT sort before an
    # earlier UTC value. 14:00-04:00 == 18:00Z is later than 17:00+00:00.
    with _open(tmp_path) as store:
        repo_id = store.ensure_repo(tmp_path)
        store.record_verification_event(
            repo_id=repo_id, commit_sha="e" * 40, kind="test_pass",
            verified_at="2026-06-25T17:00:00+00:00", actor=None, source="warpline",
        )
        store.record_verification_event(
            repo_id=repo_id, commit_sha="f" * 40, kind="test_pass",
            verified_at="2026-06-25T14:00:00-04:00", actor=None, source="warpline",
        )
        events = store.list_verification_events(tmp_path)
        # UTC 17:00 (e) is earlier than UTC 18:00 (f) -> e first.
        assert [ev["commit_sha"] for ev in events] == ["e" * 40, "f" * 40]


def test_list_change_events_for_key_ids_filters(tmp_path: Path) -> None:
    with _open(tmp_path) as store:
        repo_id = store.ensure_repo(tmp_path)
        k1 = store.ensure_entity_key(repo_id, "python:function:m.py::f", None, "1" * 40)
        k2 = store.ensure_entity_key(repo_id, "python:function:m.py::g", None, "2" * 40)
        for kid, sha in ((k1, "1" * 40), (k2, "2" * 40)):
            store.append_change_event(
                repo_id=repo_id, entity_key_id=kid, commit_sha=sha, path="m.py",
                change_kind="modified", actor="dev", changed_at="2026-06-25T08:00:00+00:00",
            )
        only_k1 = store.list_change_events_for_key_ids(tmp_path, [k1])
        assert {r["entity_key_id"] for r in only_k1} == {k1}
        assert store.list_change_events_for_key_ids(tmp_path, []) == []


def test_list_change_events_for_key_ids_is_oldest_first(tmp_path: Path) -> None:
    # Ordering is load-bearing: compose_verification_freshness treats
    # entity_change_commits[-1] as the LATEST change. A wrong ORDER BY would make
    # the OLDEST change the "latest" and silently report stale-as-fresh.
    with _open(tmp_path) as store:
        repo_id = store.ensure_repo(tmp_path)
        k = store.ensure_entity_key(repo_id, "python:function:m.py::f", None, "1" * 40)
        store.append_change_event(
            repo_id=repo_id, entity_key_id=k, commit_sha="1" * 40, path="m.py",
            change_kind="modified", actor="dev", changed_at="2026-06-25T08:00:00+00:00",
        )
        store.append_change_event(
            repo_id=repo_id, entity_key_id=k, commit_sha="2" * 40, path="n.py",
            change_kind="modified", actor="dev", changed_at="2026-06-25T20:00:00+00:00",
        )
        rows = store.list_change_events_for_key_ids(tmp_path, [k])
        assert [r["commit_sha"] for r in rows] == ["1" * 40, "2" * 40]  # oldest-first
