"""Rung 1b: working-context anchor columns (schema v2).

The anchor (``detected_branch`` / ``detected_head_sha`` / ``detected_at`` /
``detected_context``) records the DETECTION act on ``change_events`` — orthogonal
to the SEI (entity identity). These tests lock the four behaviours the plan
names: branch detection on ingest, the honest ``detected_context`` signal
(clean / working_tree_dirty / detached_head, M8/E4), the B3 backfill all-NULL
rule (reconstruction is not detection), the store read surface, the v1→v2
migration, and the M10 additive-column non-regression for the read commands.

These require the Rung 1a migration runner (the v2 anchor columns arrive through
``MIGRATIONS``, not the frozen base SCHEMA).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from conftest import commit as _commit
from conftest import git as _git
from conftest import init_repo as _init_repo

from warpline import commands
from warpline.git import backfill, ingest_commit
from warpline.store import SCHEMA, WarplineStore, default_store_path


def _events(store: WarplineStore, repo: Path) -> list[dict[str, object]]:
    return store.list_change_events(repo)


def test_ingest_on_branch_records_branch_head_and_context(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    sha = _commit(repo, "a.py", "x = 1\n")
    branch = _git(repo, "rev-parse", "--abbrev-ref", "HEAD")

    with WarplineStore.open(default_store_path(repo)) as store:
        ingest_commit(store, repo, sha)
        rows = _events(store, repo)

    assert rows, "ingest should record at least one change event"
    for row in rows:
        assert row["detected_branch"] == branch
        assert row["detected_head_sha"] == sha
        assert row["detected_at"] is not None
        # A freshly-committed clean tree.
        assert row["detected_context"] == "clean"


def test_ingest_with_dirty_work_tree_records_working_tree_dirty(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    sha = _commit(repo, "a.py", "x = 1\n")
    # Leave an uncommitted change to a TRACKED file at detection time (E4): the
    # working tree that produced this detection is unstable.
    (repo / "a.py").write_text("x = 999\n", encoding="utf-8")

    with WarplineStore.open(default_store_path(repo)) as store:
        ingest_commit(store, repo, sha)
        rows = _events(store, repo)

    assert rows
    for row in rows:
        assert row["detected_context"] == "working_tree_dirty"
        # head_sha is the stable committed HEAD; the dirty signal lives in context,
        # never in a false-precise / NULL head_sha.
        assert row["detected_head_sha"] == sha
        assert row["detected_branch"] is not None


def test_ingest_on_detached_head_records_null_branch_and_detached_context(
    tmp_path: Path,
) -> None:
    repo = _init_repo(tmp_path)
    _commit(repo, "a.py", "x = 1\n")
    sha = _commit(repo, "a.py", "x = 2\n")
    _git(repo, "checkout", "--detach", sha)

    with WarplineStore.open(default_store_path(repo)) as store:
        ingest_commit(store, repo, sha)
        rows = _events(store, repo)

    assert rows
    for row in rows:
        assert row["detected_branch"] is None
        assert row["detected_context"] == "detached_head"
        assert row["detected_head_sha"] == sha
        assert row["detected_at"] is not None


def test_backfill_leaves_all_anchor_columns_null(tmp_path: Path) -> None:
    """B3: backfill is reconstruction, not detection — ALL anchor columns NULL."""
    repo = _init_repo(tmp_path)
    _commit(repo, "a.py", "x = 1\n")
    _commit(repo, "a.py", "x = 2\n")

    with WarplineStore.open(default_store_path(repo)) as store:
        backfill(store, repo)
        rows = _events(store, repo)

    assert rows, "backfill should record change events"
    for row in rows:
        assert row["detected_branch"] is None
        assert row["detected_head_sha"] is None
        assert row["detected_at"] is None
        assert row["detected_context"] is None


def test_store_read_surfaces_anchor_fields(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    sha = _commit(repo, "a.py", "x = 1\n")

    with WarplineStore.open(default_store_path(repo)) as store:
        ingest_commit(store, repo, sha)
        list_rows = store.list_change_events(repo)
        timeline_rows = store.timeline(repo, "file:a.py")

    anchor_keys = {
        "detected_branch",
        "detected_head_sha",
        "detected_at",
        "detected_context",
    }
    assert list_rows and anchor_keys <= set(list_rows[0])
    assert timeline_rows and anchor_keys <= set(timeline_rows[0])


def test_v1_db_opened_by_v2_client_migrates_and_old_rows_read_null(
    tmp_path: Path,
) -> None:
    """A DB materialized at the frozen base SCHEMA (no anchor columns) upgrades on
    open; rows written before the upgrade read NULL anchors (honest unavailable)."""
    db = default_store_path(tmp_path / "repo")
    db.parent.mkdir(parents=True, exist_ok=True)

    # Simulate a pre-v2 DB: base SCHEMA only, no anchor columns, with one
    # hand-inserted change_event under the v1 column set.
    raw = sqlite3.connect(db)
    raw.row_factory = sqlite3.Row
    raw.executescript(SCHEMA)
    raw.execute(
        "INSERT INTO repos(id, root) VALUES ('r', '/x')",
    )
    raw.execute(
        "INSERT INTO entity_keys(repo_id, locator, sei) VALUES ('r', 'file:legacy.py', NULL)"
    )
    key_id = int(
        raw.execute("SELECT id FROM entity_keys WHERE locator='file:legacy.py'").fetchone()[
            "id"
        ]
    )
    raw.execute(
        """
        INSERT INTO change_events(
          repo_id, entity_key_id, commit_sha, path, change_kind, actor, changed_at
        ) VALUES ('r', ?, 'deadbeef', 'legacy.py', 'modified', 'a@b', '2020-01-01T00:00:00')
        """,
        (key_id,),
    )
    raw.commit()
    cols_before = {r["name"] for r in raw.execute("PRAGMA table_info(change_events)")}
    raw.close()
    assert "detected_context" not in cols_before

    with WarplineStore.open(db) as store:
        assert store.schema_version() == 3
        row = store.conn.execute(
            "SELECT detected_branch, detected_head_sha, detected_at, detected_context "
            "FROM change_events WHERE commit_sha='deadbeef'"
        ).fetchone()
        assert row["detected_branch"] is None
        assert row["detected_head_sha"] is None
        assert row["detected_at"] is None
        assert row["detected_context"] is None


def test_change_list_and_timeline_non_regression_on_migrated_db(tmp_path: Path) -> None:
    """M10: change_list / entity_timeline return valid output with the new columns
    present on a v1-then-migrated DB (additive columns do not break the reads)."""
    repo = _init_repo(tmp_path)
    sha = _commit(repo, "a.py", "x = 1\n")

    # Materialize the base SCHEMA first (pre-v2), then let the command's
    # WarplineStore.open() run the v2 migration on top.
    db = default_store_path(repo)
    db.parent.mkdir(parents=True, exist_ok=True)
    raw = sqlite3.connect(db)
    raw.executescript(SCHEMA)
    raw.commit()
    raw.close()

    with WarplineStore.open(db) as store:
        ingest_commit(store, repo, sha)

    change_out = commands.change_list(repo)
    assert change_out["data"]["items"]
    timeline_out = commands.entity_timeline(repo, entity="file:a.py")
    assert timeline_out["data"]["items"]
