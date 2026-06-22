from __future__ import annotations

import hashlib
import logging
import os
import sqlite3
from collections.abc import Callable, Iterable
from pathlib import Path
from types import TracebackType
from typing import NamedTuple

logger = logging.getLogger(__name__)

# Minimum bundled-SQLite floor. Justification: ``create_edge_snapshot`` uses the
# ``RETURNING`` clause (store.py), first available in SQLite 3.35.0. No migration
# in this project drops a column, so the floor is RETURNING, not ALTER … DROP COLUMN.
_MIN_SQLITE_VERSION = (3, 35, 0)

# R8/M7 co-change fan-out cap. A commit touching MORE than this many distinct
# entities skips pair generation entirely: when everything changes together the
# pairwise coupling signal is near zero and O(n^2) pair writes are pure noise.
# The cap is applied per-commit (the caller accumulates ids across the full
# path+locator loop and calls update_co_change_pairs once per commit, M7).
_CO_CHANGE_FANOUT_CAP = 30

# After Rung 1a, ``SCHEMA`` DDL is FROZEN. All schema changes (added columns,
# new tables) go through ``MIGRATIONS`` — never by editing ``SCHEMA``. ``SCHEMA``
# remains only the fresh-DB base-table definition (idempotent ``IF NOT EXISTS``).
#
# Fresh-DB WAL note: ``executescript(SCHEMA)`` runs ``PRAGMA journal_mode=WAL``
# via an implicit-commit ``executescript`` — intentional, and deliberately
# OUTSIDE the per-migration ``BEGIN IMMEDIATE`` pattern (Python's executescript
# issues an implicit COMMIT, so the migration runner uses ``conn.execute`` per
# statement instead; see ``_run_migrations``).
SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS meta (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
INSERT OR IGNORE INTO meta(key, value) VALUES ('schema_version', '1');
CREATE TABLE IF NOT EXISTS repos (
  id TEXT PRIMARY KEY,
  root TEXT NOT NULL,
  remote_fingerprint TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS entity_keys (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  repo_id TEXT NOT NULL,
  locator TEXT NOT NULL,
  sei TEXT,
  first_seen_commit TEXT,
  last_seen_commit TEXT,
  FOREIGN KEY(repo_id) REFERENCES repos(id)
);
CREATE UNIQUE INDEX IF NOT EXISTS entity_keys_unique
  ON entity_keys(repo_id, locator, COALESCE(sei, ''));
CREATE TABLE IF NOT EXISTS commit_refs (
  repo_id TEXT NOT NULL,
  sha TEXT NOT NULL,
  parents_json TEXT NOT NULL,
  author TEXT NOT NULL,
  authored_at TEXT NOT NULL,
  committed_at TEXT NOT NULL,
  PRIMARY KEY(repo_id, sha)
);
CREATE TABLE IF NOT EXISTS change_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  repo_id TEXT NOT NULL,
  entity_key_id INTEGER NOT NULL,
  commit_sha TEXT NOT NULL,
  path TEXT NOT NULL,
  change_kind TEXT NOT NULL,
  actor TEXT NOT NULL,
  changed_at TEXT NOT NULL,
  hunk_summary TEXT NOT NULL DEFAULT '',
  UNIQUE(repo_id, entity_key_id, commit_sha, path, change_kind),
  FOREIGN KEY(entity_key_id) REFERENCES entity_keys(id)
);
CREATE TABLE IF NOT EXISTS edge_snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  repo_id TEXT NOT NULL,
  commit_sha TEXT NOT NULL,
  source TEXT NOT NULL,
  source_version TEXT NOT NULL,
  captured_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  completeness TEXT NOT NULL,
  UNIQUE(repo_id, commit_sha, source)
);
CREATE TABLE IF NOT EXISTS snapshot_edges (
  snapshot_id INTEGER NOT NULL,
  source_entity_key_id INTEGER NOT NULL,
  target_entity_key_id INTEGER NOT NULL,
  edge_kind TEXT NOT NULL,
  confidence TEXT NOT NULL,
  PRIMARY KEY(snapshot_id, source_entity_key_id, target_entity_key_id, edge_kind),
  FOREIGN KEY(snapshot_id) REFERENCES edge_snapshots(id)
);
CREATE TABLE IF NOT EXISTS health_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  repo_id TEXT NOT NULL,
  code TEXT NOT NULL,
  message TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""

WARPLINE_GITIGNORE_CONTENTS = """\
# Warpline .gitignore - local runtime store
# Tracked: this .gitignore only.

warpline.db
*.db-wal
*.db-shm
*-wal
*-shm
*.lock
tmp/
"""


class Migration(NamedTuple):
    """One ordered, forward-only schema migration.

    ``apply`` runs its ``conn.execute(...)`` statements INSIDE an already-open
    ``BEGIN IMMEDIATE`` transaction owned by the runner; it must NOT call
    ``executescript`` (which would issue an implicit COMMIT and break the
    transaction's atomicity, R3) and must NOT commit/begin itself.
    """

    version: int
    apply: Callable[[sqlite3.Connection], None]


def _migrate_v2_anchor_columns(conn: sqlite3.Connection) -> None:
    """v2 (Rung 1b): working-context anchor columns on ``change_events``.

    The anchor identifies the **detection act** (a change episode, verb-moment),
    orthogonal to the SEI (entity identity, noun) — so it lives on
    ``change_events``, never on ``entity_keys``. All columns are NULLable with no
    default (O(1) metadata-only ALTERs): a backfilled or pre-v2 row reads NULL,
    which the honesty invariant surfaces as ``unavailable`` working-context
    rather than a clean-looking default.

    - ``detected_branch``    — git symbolic-ref short name; NULL if detached.
    - ``detected_head_sha``  — HEAD sha AT DETECTION (working context; distinct
      from ``commit_sha`` = the introducing commit).
    - ``detected_at``        — ISO-8601 UTC detection timestamp (distinct from
      ``changed_at`` = author time).
    - ``detected_context``   — honest E4/M8 signal carrier, one of
      ``clean`` / ``working_tree_dirty`` / ``detached_head`` (NULL on
      backfilled/pre-v2 rows). Subsumes the detached-HEAD case so a NULL
      ``detected_head_sha`` is never overloaded to mean "detached".
    """

    conn.execute("ALTER TABLE change_events ADD COLUMN detected_branch TEXT")
    conn.execute("ALTER TABLE change_events ADD COLUMN detected_head_sha TEXT")
    conn.execute("ALTER TABLE change_events ADD COLUMN detected_at TEXT")
    conn.execute("ALTER TABLE change_events ADD COLUMN detected_context TEXT")


def _migrate_v3_co_change_pairs(conn: sqlite3.Connection) -> None:
    """v3 (Rung 2 Track A): temporal co-change coupling graph.

    ``co_change_pairs`` records, for each unordered pair of warpline-local
    ``entity_key_id``s, how many times they changed together in the same commit
    — a co-occurrence fact warpline OWNS (derived from its own ``change_events``),
    not a mirror of any sibling. Pairs are stored canonically (``a < b``) so each
    unordered pair has exactly one row.

    Per-entity totals are NOT denormalized here: they come from ``change_events``
    aggregation at read time (``co_change_partners``). If read cost ever demands
    it, denormalized ``total_a``/``total_b`` columns are an additive later
    migration — the co-change read cost note in the plan.

    SEI-orthogonality: the table keys on ``entity_key_id`` integers only and mints
    no identifier; the SEI is joined from ``entity_keys`` at read time, never
    stored here.
    """

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS co_change_pairs (
          repo_id          TEXT NOT NULL,
          entity_key_id_a  INTEGER NOT NULL,
          entity_key_id_b  INTEGER NOT NULL,
          co_change_count  INTEGER NOT NULL,
          last_co_change   TEXT,
          last_commit_sha  TEXT,
          PRIMARY KEY (repo_id, entity_key_id_a, entity_key_id_b)
        )
        """
    )


# Ordered, forward-only migrations. Each step's ``version`` is strictly greater
# than the previous. v2 (anchor columns) lands in Rung 1b; v3 (co_change_pairs)
# in Rung 2 Track A.
#
# Migration-ordering gate (B5): v3 MUST NOT precede v2 on disk — a DB opened in
# the gap would land at user_version=3 and permanently skip v2. The ordered list
# is the enforcement: v2 always runs before v3 for any DB below 2.
MIGRATIONS: list[Migration] = [
    Migration(version=2, apply=_migrate_v2_anchor_columns),
    Migration(version=3, apply=_migrate_v3_co_change_pairs),
]

# Highest schema version this build knows how to produce. Equals the base
# ``SCHEMA`` (1) plus the max migration version. A DB whose ``user_version``
# exceeds this was written by a newer build — reads stay safe (additive-only
# history), so the runner WARNS rather than failing.
HIGHEST_KNOWN_VERSION = max((m.version for m in MIGRATIONS), default=1)


def default_store_path(repo: Path, base_dir: Path | None = None) -> Path:
    root = repo.resolve()
    state = base_dir or root / ".weft" / "warpline"
    return state / "warpline.db"


def _ensure_store_gitignore(store_dir: Path) -> None:
    gitignore = store_dir / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text(WARPLINE_GITIGNORE_CONTENTS, encoding="utf-8")


# Sentinel repo_id for store-level (repo-agnostic) health events written during
# open()/migration, where no repo Path is in scope.
_STORE_HEALTH_REPO_ID = "__store__"


def _meta_schema_version(conn: sqlite3.Connection) -> str | None:
    row = conn.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()
    return None if row is None else str(row["value"])


def _store_health(conn: sqlite3.Connection, code: str, message: str) -> None:
    """Record a store-level health event (open/migration path, no repo in scope)."""

    conn.execute(
        "INSERT INTO health_log(repo_id, code, message) VALUES (?, ?, ?)",
        (_STORE_HEALTH_REPO_ID, code, message),
    )


def _later_marker(
    last_a: str | None,
    sha_a: str | None,
    last_b: str | None,
    sha_b: str | None,
) -> tuple[str | None, str | None]:
    """Pick the chronologically-later ``(last_co_change, last_commit_sha)`` pair.

    Used when two co_change_pairs rows merge (#3 twin repoint): the recency
    marker of the later co-change wins, and a populated timestamp always beats a
    NULL one — the same "never regress a marker to NULL" rule the live upsert
    follows (#7). Equal/incomparable timestamps keep side A deterministically.
    """

    if last_b is None:
        return last_a, sha_a
    if last_a is None:
        return last_b, sha_b
    return (last_b, sha_b) if str(last_b) > str(last_a) else (last_a, sha_a)


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (name,),
    ).fetchone()
    return row is not None


def _change_events_has_anchor_columns(conn: sqlite3.Connection) -> bool:
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(change_events)")}
    return {
        "detected_branch",
        "detected_head_sha",
        "detected_at",
        "detected_context",
    } <= cols


def _schema_presence_floor(conn: sqlite3.Connection, claimed: int) -> int:
    """Verified floor for an adopted ``meta.schema_version`` (#9 guard).

    A ``meta.schema_version`` marker is a CLAIM, not proof. This walks the
    per-version object requirements UP from the base (v1) and stops at the first
    KNOWN version (≤ ``HIGHEST_KNOWN_VERSION``) whose objects are missing,
    returning the last fully-present version — so a DB marked v3 that lacks
    ``co_change_pairs`` floors to v2 (or v1 if the anchor columns are also gone)
    and the runner re-applies the missing steps instead of trusting a marker the
    disk does not back up.

    Two non-floor cases are honoured deliberately:

    - Every checkable (≤ HIGHEST_KNOWN) object is present → the marker is TRUSTED
      and ``claimed`` is returned UNCHANGED. A genuinely-newer DB (``claimed`` >
      HIGHEST_KNOWN whose extra v(N>3) objects we cannot enumerate) keeps its
      ahead marker so the ``> HIGHEST_KNOWN`` branch still fires SCHEMA_VERSION_AHEAD.
    - ``claimed`` below a check simply skips that check.

    New versions add their object presence check here alongside their migration.
    """

    floor = 1
    # v2 (Rung 1b): anchor columns on change_events.
    if claimed >= 2:
        if not _change_events_has_anchor_columns(conn):
            return floor
        floor = 2
    # v3 (Rung 2 Track A): the co_change_pairs table.
    if claimed >= 3:
        if not _table_exists(conn, "co_change_pairs"):
            return floor
        floor = 3
    # All checkable objects present: trust the marker as-is (never DOWNGRADE a
    # legitimately-ahead version we simply cannot fully verify).
    return claimed


def _run_migrations(conn: sqlite3.Connection) -> None:
    """Apply ordered forward-only migrations from ``user_version`` to HIGHEST_KNOWN.

    Atomicity (R3): each step runs inside its own explicit ``BEGIN IMMEDIATE`` /
    ``COMMIT``; the step's ``apply`` callable uses ``conn.execute`` only (never
    ``executescript``). ``PRAGMA user_version`` and the ``meta`` row are updated
    in the SAME transaction. Concurrent ``open()`` calls block on the RESERVED
    lock (busy_timeout), then re-read ``user_version`` and skip applied steps.
    """

    current = int(conn.execute("PRAGMA user_version").fetchone()[0])

    # M9 / legacy reconcile: a DB created before the runner existed has
    # user_version==0 but a meta.schema_version row. Adopt the meta value so we
    # do not re-run already-applied schema. The expected legacy value is '1'
    # (base SCHEMA); any other value is from a divergent/newer writer — warn and
    # adopt it before running steps with version > that.
    if current == 0:
        meta_version = _meta_schema_version(conn)
        if meta_version is None or meta_version == "1":
            # Fresh DB or pre-runner legacy v1: the expected baseline. The base
            # SCHEMA always inserts schema_version='1', so meta_version is None
            # only on a corrupt/empty meta — treat as baseline 1 either way.
            current = 1
        else:
            try:
                current = int(meta_version)
            except (TypeError, ValueError):
                logger.warning(
                    "warpline store: non-integer meta.schema_version %r with "
                    "user_version=0; adopting baseline version 1",
                    meta_version,
                )
                _store_health(
                    conn,
                    "MIGRATION_META_UNPARSEABLE",
                    f"meta.schema_version={meta_version!r} not an int; adopted 1",
                )
                current = 1
            else:
                logger.warning(
                    "warpline store: user_version=0 but meta.schema_version=%s "
                    "(expected '1'); adopting %d before running later migrations",
                    meta_version,
                    current,
                )
                _store_health(
                    conn,
                    "MIGRATION_META_RECONCILE",
                    f"user_version=0, meta.schema_version={meta_version}; adopted {current}",
                )
                # #9: the meta marker is a CLAIM, not proof. A DB that says
                # version N but is MISSING the schema objects N implies (e.g.
                # meta='3' with no co_change_pairs table) would otherwise come up
                # "at v3" and the first coupling query would raise `no such
                # table`. Verify the objects actually present and DROP current to
                # the highest version whose objects all exist, so the missing
                # migrations re-run from a safe floor instead of being skipped on
                # a false marker.
                present_floor = _schema_presence_floor(conn, current)
                if present_floor < current:
                    logger.warning(
                        "warpline store: meta.schema_version=%d but on-disk schema "
                        "objects only present through v%d; re-running migrations "
                        "from the verified floor",
                        current,
                        present_floor,
                    )
                    _store_health(
                        conn,
                        "MIGRATION_META_SCHEMA_GAP",
                        f"meta.schema_version={current} but objects present only "
                        f"through {present_floor}; re-running from floor",
                    )
                    current = present_floor
        # Persist the reconciled version once so the next open() short-circuits.
        conn.execute(f"PRAGMA user_version = {current}")
        conn.commit()

    if current > HIGHEST_KNOWN_VERSION:
        # Newer writer touched this DB. Reads are still safe (additive-only
        # history); warn, record to health_log, and proceed without applying.
        logger.warning(
            "warpline store: on-disk schema version %d exceeds highest known %d; "
            "this build is older than the writer — reads remain safe",
            current,
            HIGHEST_KNOWN_VERSION,
        )
        _store_health(
            conn,
            "SCHEMA_VERSION_AHEAD",
            f"on-disk version {current} > highest known {HIGHEST_KNOWN_VERSION}",
        )
        conn.commit()
        return

    for migration in MIGRATIONS:
        if migration.version <= current:
            continue
        conn.execute("BEGIN IMMEDIATE")
        try:
            # Re-read under the RESERVED lock: a concurrent writer may have
            # applied this (or a later) step while we blocked on busy_timeout.
            locked_version = int(conn.execute("PRAGMA user_version").fetchone()[0])
            if migration.version <= locked_version:
                conn.execute("COMMIT")
                current = locked_version
                continue
            migration.apply(conn)
            conn.execute(f"PRAGMA user_version = {migration.version}")
            conn.execute(
                "UPDATE meta SET value = ? WHERE key = 'schema_version'",
                (str(migration.version),),
            )
            conn.execute("COMMIT")
        except BaseException:
            conn.execute("ROLLBACK")
            raise
        current = migration.version


class WarplineStore:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    @classmethod
    def open(cls, path: Path) -> WarplineStore:
        if sqlite3.sqlite_version_info < _MIN_SQLITE_VERSION:
            have = ".".join(str(p) for p in sqlite3.sqlite_version_info)
            need = ".".join(str(p) for p in _MIN_SQLITE_VERSION)
            raise RuntimeError(
                f"warpline requires SQLite >= {need} (RETURNING clause); "
                f"this Python is bundled with SQLite {have}"
            )
        path.parent.mkdir(parents=True, exist_ok=True)
        _ensure_store_gitignore(path.parent)
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        # Connection hardening. journal_mode=WAL is also set by SCHEMA below;
        # foreign_keys/busy_timeout/synchronous are per-connection pragmas.
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 5000")
        conn.execute("PRAGMA synchronous = NORMAL")
        # Fresh-DB base tables (idempotent IF NOT EXISTS). The implicit-commit
        # executescript is intentional here and outside the migration pattern.
        conn.executescript(SCHEMA)
        _run_migrations(conn)
        return cls(conn)

    def __enter__(self) -> WarplineStore:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.conn.close()

    def schema_version(self) -> int:
        row = self.conn.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()
        if row is None:
            raise RuntimeError("missing schema_version")
        return int(row["value"])

    def _repo_id(self, repo: Path) -> str:
        return hashlib.sha256(str(repo.resolve()).encode("utf-8")).hexdigest()

    def ensure_repo(self, repo: Path) -> str:
        repo_id = self._repo_id(repo)
        root = str(repo.resolve())
        self.conn.execute(
            "INSERT OR IGNORE INTO repos(id, root, remote_fingerprint) VALUES (?, ?, ?)",
            (repo_id, root, None),
        )
        self.conn.commit()
        return repo_id

    def upsert_commit(self, repo_id: str, meta: dict[str, str]) -> None:
        self.conn.execute(
            """
            INSERT OR IGNORE INTO commit_refs(
              repo_id, sha, parents_json, author, authored_at, committed_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                repo_id,
                meta["sha"],
                meta["parents_json"],
                meta["author"],
                meta["authored_at"],
                meta["committed_at"],
            ),
        )
        self.conn.commit()

    def ensure_entity_key(
        self,
        repo_id: str,
        locator: str,
        sei: str | None,
        commit_sha: str,
    ) -> int:
        self.conn.execute(
            """
            INSERT OR IGNORE INTO entity_keys(
              repo_id, locator, sei, first_seen_commit, last_seen_commit
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (repo_id, locator, sei, commit_sha, commit_sha),
        )
        self.conn.execute(
            """
            UPDATE entity_keys
               SET last_seen_commit = ?
             WHERE repo_id = ?
               AND locator = ?
               AND COALESCE(sei, '') = COALESCE(?, '')
            """,
            (commit_sha, repo_id, locator, sei),
        )
        row = self.conn.execute(
            """
            SELECT id FROM entity_keys
             WHERE repo_id = ?
               AND locator = ?
               AND COALESCE(sei, '') = COALESCE(?, '')
            """,
            (repo_id, locator, sei),
        ).fetchone()
        if row is None:
            raise RuntimeError(f"failed to create entity key for {locator}")
        self.conn.commit()
        return int(row["id"])

    def null_sei_entity_keys(self, repo: Path, limit: int = 200) -> list[dict[str, object]]:
        """Entity keys whose SEI is still NULL, bounded and id-ordered.

        Rung 1c self-healing sweep input. A row minted while loomweave was down
        keeps ``sei IS NULL`` forever (the UNIQUE index treats a null-sei row and
        a resolved-sei row for the same locator as distinct identities), so this
        is the worklist the re-resolution sweep pages through. Ordered by ``id``
        for deterministic, resumable paging.
        """

        repo_id = self._repo_id(repo)
        rows = self.conn.execute(
            """
            SELECT id, locator FROM entity_keys
             WHERE repo_id = ? AND sei IS NULL
             ORDER BY id
             LIMIT ?
            """,
            (repo_id, int(limit)),
        ).fetchall()
        return [dict(row) for row in rows]

    def reresolve_entity_key_sei(
        self,
        repo_id: str,
        null_key_id: int,
        locator: str,
        resolved_sei: str,
    ) -> dict[str, str]:
        """Idempotent UPDATE-or-merge of a null-sei entity key to a resolved SEI.

        Never re-mints (R11). Returns ``{"action": ...}`` where action is:

        - ``resolved`` — the null row was repointed in place (no twin existed).
        - ``merged``   — a resolved-sei twin for the same locator already
          existed; its row is the survivor. ``change_events`` were repointed from
          the null key to the twin, any rows colliding on the ``change_events``
          UNIQUE constraint had their **null-keyed duplicate DELETED** (M5: the
          resolved-keyed row is canonical), the orphan null ``entity_keys`` row
          was deleted, and ``min(first_seen_commit)`` / ``max(last_seen_commit)``
          were carried onto the survivor.
        - ``noop``     — the row no longer matches ``sei IS NULL`` (already healed
          on a prior pass); convergent re-run.

        All steps run inside one ``BEGIN IMMEDIATE`` transaction.
        """

        self.conn.execute("BEGIN IMMEDIATE")
        try:
            row = self.conn.execute(
                "SELECT id, first_seen_commit, last_seen_commit FROM entity_keys "
                "WHERE id = ? AND repo_id = ? AND sei IS NULL",
                (null_key_id, repo_id),
            ).fetchone()
            if row is None:
                # Already healed (or never null) — convergent no-op.
                self.conn.execute("COMMIT")
                return {"action": "noop"}
            try:
                self.conn.execute(
                    "UPDATE entity_keys SET sei = ? WHERE id = ? AND sei IS NULL",
                    (resolved_sei, null_key_id),
                )
            except sqlite3.IntegrityError:
                # A resolved-sei twin for this (repo, locator) already exists; it
                # is the survivor. Repoint change_events, drop colliding null-keyed
                # duplicates, delete the orphan null key, carry first/last seen.
                action = self._merge_into_twin(
                    repo_id=repo_id,
                    null_key_id=null_key_id,
                    locator=locator,
                    resolved_sei=resolved_sei,
                    null_first_seen=row["first_seen_commit"],
                    null_last_seen=row["last_seen_commit"],
                )
                self.conn.execute("COMMIT")
                return {"action": action}
            self.conn.execute("COMMIT")
            return {"action": "resolved"}
        except BaseException:
            self.conn.execute("ROLLBACK")
            raise

    def _merge_into_twin(
        self,
        *,
        repo_id: str,
        null_key_id: int,
        locator: str,
        resolved_sei: str,
        null_first_seen: str | None,
        null_last_seen: str | None,
    ) -> str:
        """Merge a null-sei key into its resolved-sei twin (caller holds the txn)."""

        twin = self.conn.execute(
            "SELECT id, first_seen_commit, last_seen_commit FROM entity_keys "
            "WHERE repo_id = ? AND locator = ? AND sei = ?",
            (repo_id, locator, resolved_sei),
        ).fetchone()
        if twin is None:  # pragma: no cover - IntegrityError implies a twin exists
            raise RuntimeError(
                f"reresolve: IntegrityError but no resolved twin for {locator!r}"
            )
        twin_id = int(twin["id"])

        # Repoint change_events one row at a time so a UNIQUE collision on the
        # twin (same commit/path/change_kind already recorded under the resolved
        # key) deletes the null-keyed duplicate rather than aborting the repoint.
        null_events = self.conn.execute(
            "SELECT id FROM change_events WHERE entity_key_id = ?",
            (null_key_id,),
        ).fetchall()
        for event in null_events:
            try:
                self.conn.execute(
                    "UPDATE change_events SET entity_key_id = ? WHERE id = ?",
                    (twin_id, event["id"]),
                )
            except sqlite3.IntegrityError:
                # The resolved-keyed row is canonical (M5): drop the null-keyed
                # duplicate. Any divergent data on it (hunk_summary, actor) is
                # deliberately discarded — explicit, documented data loss (Q7).
                self.conn.execute(
                    "DELETE FROM change_events WHERE id = ?", (event["id"],)
                )

        # Carry first/last seen onto the survivor: min(first), max(last) across
        # both rows. Commit SHAs are not chronologically orderable, so this is a
        # deterministic string min/max that never drops a non-null value.
        twin_first = twin["first_seen_commit"]
        twin_last = twin["last_seen_commit"]
        firsts = [
            str(v) for v in (twin_first, null_first_seen) if v is not None
        ]
        lasts = [str(v) for v in (twin_last, null_last_seen) if v is not None]
        merged_first = min(firsts) if firsts else None
        merged_last = max(lasts) if lasts else None
        self.conn.execute(
            "UPDATE entity_keys SET first_seen_commit = ?, last_seen_commit = ? WHERE id = ?",
            (merged_first, merged_last, twin_id),
        )

        # #3: co_change_pairs and snapshot_edges reference entity_key_id integers
        # but have NO foreign key, so deleting the null key would orphan their
        # rows (and any co_change_partners / snapshot read would still surface the
        # now-deleted id). Repoint them onto the survivor BEFORE the null-key
        # DELETE, merging on collision rather than leaving dangling references.
        self._repoint_co_change_pairs(repo_id, null_key_id, twin_id)
        self._repoint_snapshot_edges(null_key_id, twin_id)

        # Delete the now-orphaned null key (its events were repointed/merged).
        self.conn.execute("DELETE FROM entity_keys WHERE id = ?", (null_key_id,))
        return "merged"

    def _repoint_co_change_pairs(
        self, repo_id: str, null_key_id: int, twin_id: int
    ) -> None:
        """Repoint a null key's co_change_pairs onto its resolved twin (#3).

        co_change_pairs stores pairs canonically (``entity_key_id_a < b``). After
        repointing one endpoint from ``null_key_id`` to ``twin_id`` a row may:

        - collapse into a SELF-pair (the other endpoint already IS the twin) — a
          self-coupling is meaningless, so it is DROPPED;
        - re-canonicalize (the repointed endpoint now sorts the other side of
          ``a < b``);
        - COLLIDE with an existing twin pair for the same canonical (a, b) — the
          two are the SAME unordered pair, so their counts are SUMMED and the
          later recency marker (``last_co_change`` / ``last_commit_sha``) kept,
          never lost.

        The caller holds the BEGIN IMMEDIATE txn. We resolve every collision in
        Python (read both candidate rows, compute the merged row, delete both,
        re-insert) so the canonical PRIMARY KEY is never violated mid-flight.
        """

        rows = self.conn.execute(
            """
            SELECT entity_key_id_a, entity_key_id_b,
                   co_change_count, last_co_change, last_commit_sha
              FROM co_change_pairs
             WHERE repo_id = ? AND (entity_key_id_a = ? OR entity_key_id_b = ?)
            """,
            (repo_id, null_key_id, null_key_id),
        ).fetchall()
        for row in rows:
            old_a = int(row["entity_key_id_a"])
            old_b = int(row["entity_key_id_b"])
            # The endpoint that is NOT the null key stays; the null endpoint
            # becomes the twin.
            other = old_b if old_a == null_key_id else old_a
            # Drop the original (null-keyed) row; we re-home its data below.
            self.conn.execute(
                "DELETE FROM co_change_pairs "
                "WHERE repo_id = ? AND entity_key_id_a = ? AND entity_key_id_b = ?",
                (repo_id, old_a, old_b),
            )
            if other == twin_id:
                # Self-pair after repoint (twin co-changing with itself): drop it.
                continue
            new_a, new_b = (twin_id, other) if twin_id < other else (other, twin_id)
            existing = self.conn.execute(
                "SELECT co_change_count, last_co_change, last_commit_sha "
                "FROM co_change_pairs "
                "WHERE repo_id = ? AND entity_key_id_a = ? AND entity_key_id_b = ?",
                (repo_id, new_a, new_b),
            ).fetchone()
            if existing is None:
                self.conn.execute(
                    """
                    INSERT INTO co_change_pairs(
                      repo_id, entity_key_id_a, entity_key_id_b,
                      co_change_count, last_co_change, last_commit_sha
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        repo_id,
                        new_a,
                        new_b,
                        int(row["co_change_count"]),
                        row["last_co_change"],
                        row["last_commit_sha"],
                    ),
                )
                continue
            # Collision with an existing twin pair: SUM counts, keep the later
            # recency marker (a non-null timestamp always beats null).
            merged_count = int(existing["co_change_count"]) + int(row["co_change_count"])
            merged_last, merged_sha = _later_marker(
                existing["last_co_change"],
                existing["last_commit_sha"],
                row["last_co_change"],
                row["last_commit_sha"],
            )
            self.conn.execute(
                """
                UPDATE co_change_pairs
                   SET co_change_count = ?, last_co_change = ?, last_commit_sha = ?
                 WHERE repo_id = ? AND entity_key_id_a = ? AND entity_key_id_b = ?
                """,
                (merged_count, merged_last, merged_sha, repo_id, new_a, new_b),
            )

    def _repoint_snapshot_edges(self, null_key_id: int, twin_id: int) -> None:
        """Repoint a null key's snapshot_edges onto its resolved twin (#3).

        snapshot_edges' PRIMARY KEY is
        ``(snapshot_id, source_entity_key_id, target_entity_key_id, edge_kind)``.
        Repointing a source or target from the null key to the twin can collide
        with an edge already recorded under the twin (same snapshot/kind) or
        collapse a source==target self-edge. ``INSERT OR IGNORE`` into the
        repointed shape then deleting the null-keyed originals drops duplicates on
        collision rather than aborting the merge — the twin-keyed row is canonical
        (mirrors the change_events M5 rule).
        """

        edges = self.conn.execute(
            """
            SELECT snapshot_id, source_entity_key_id, target_entity_key_id,
                   edge_kind, confidence
              FROM snapshot_edges
             WHERE source_entity_key_id = ? OR target_entity_key_id = ?
            """,
            (null_key_id, null_key_id),
        ).fetchall()
        for edge in edges:
            self.conn.execute(
                """
                DELETE FROM snapshot_edges
                 WHERE snapshot_id = ? AND source_entity_key_id = ?
                   AND target_entity_key_id = ? AND edge_kind = ?
                """,
                (
                    edge["snapshot_id"],
                    edge["source_entity_key_id"],
                    edge["target_entity_key_id"],
                    edge["edge_kind"],
                ),
            )
            new_source = (
                twin_id
                if int(edge["source_entity_key_id"]) == null_key_id
                else int(edge["source_entity_key_id"])
            )
            new_target = (
                twin_id
                if int(edge["target_entity_key_id"]) == null_key_id
                else int(edge["target_entity_key_id"])
            )
            # INSERT OR IGNORE: a collision with an existing twin-keyed edge (or a
            # duplicate produced by this very repoint) is dropped, not raised.
            self.conn.execute(
                """
                INSERT OR IGNORE INTO snapshot_edges(
                  snapshot_id, source_entity_key_id, target_entity_key_id,
                  edge_kind, confidence
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    edge["snapshot_id"],
                    new_source,
                    new_target,
                    edge["edge_kind"],
                    edge["confidence"],
                ),
            )

    def list_entity_keys(self, repo: Path) -> list[dict[str, object]]:
        repo_id = self._repo_id(repo)
        rows = self.conn.execute(
            """
            SELECT id, locator, sei, first_seen_commit, last_seen_commit
              FROM entity_keys
             WHERE repo_id = ?
             ORDER BY id
            """,
            (repo_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def append_change_event(
        self,
        *,
        repo_id: str,
        entity_key_id: int,
        commit_sha: str,
        path: str,
        change_kind: str,
        actor: str,
        changed_at: str,
        hunk_summary: str = "",
        detected_branch: str | None = None,
        detected_head_sha: str | None = None,
        detected_at: str | None = None,
        detected_context: str | None = None,
    ) -> None:
        # Working-context anchor (v2) is optional: unsupplied → NULL, which is
        # backward compatible and reads as ``unavailable`` (never a clean
        # default). Columns are named explicitly so the additive v2 columns
        # cannot shift positionally (M10).
        self.conn.execute(
            """
            INSERT OR IGNORE INTO change_events(
              repo_id, entity_key_id, commit_sha, path, change_kind,
              actor, changed_at, hunk_summary,
              detected_branch, detected_head_sha, detected_at, detected_context
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                repo_id,
                entity_key_id,
                commit_sha,
                path,
                change_kind,
                actor,
                changed_at,
                hunk_summary,
                detected_branch,
                detected_head_sha,
                detected_at,
                detected_context,
            ),
        )
        self.conn.commit()

    def commit_has_change_events(self, repo_id: str, commit_sha: str) -> bool:
        """Whether this commit already has any recorded change_events (#2).

        The re-ingest idempotence guard. ``append_change_event`` is idempotent
        (``INSERT OR IGNORE``) but ``update_co_change_pairs`` is NOT — its counter
        increments unconditionally — so re-ingesting a commit would double-count
        every pair and diverge from ``rebuild_co_change_pairs`` (which dedupes by
        commit group). The caller checks this BEFORE writing any events so that a
        commit already in the store skips co-change derivation entirely, making a
        re-run of ``ingest-commit <sha>`` a no-op for counting.
        """

        row = self.conn.execute(
            "SELECT 1 FROM change_events WHERE repo_id = ? AND commit_sha = ? LIMIT 1",
            (repo_id, commit_sha),
        ).fetchone()
        return row is not None

    def list_change_events(
        self,
        repo: Path,
        commit_shas: set[str] | None = None,
        *,
        since: str | None = None,
        until: str | None = None,
    ) -> list[dict[str, object]]:
        # ``since``/``until`` (inclusive, on ``changed_at``) are the time_window
        # frame's store support (M4): the COP ``time_window`` frame kind resolves
        # change events by author-time bounds. Additive optional kwargs — existing
        # callers (commit-sha or unfiltered reads) are unaffected.
        #
        # #8 mixed-offset correctness: ``changed_at`` is git ``%aI`` — ISO-8601
        # WITH a tz offset. A raw string ``>=``/``<=`` / ORDER BY would sort
        # "2024-01-01T09:00:00-05:00" (14:00 UTC) BEFORE
        # "2024-01-01T10:00:00+00:00" (10:00 UTC), which is wrong. SQLite's
        # ``datetime()`` parses the offset and normalizes to UTC, so we compare
        # and order on the normalized instant for the time-window bounds. We
        # COALESCE back to the raw string so a value ``datetime()`` cannot parse
        # (it returns NULL) still sorts deterministically by its lexical form
        # rather than vanishing — an honest fallback, never a silent drop. The
        # since/until bounds are normalized on BOTH sides for the same reason.
        repo_id = self._repo_id(repo)
        params: list[object] = [repo_id]
        clauses = ""
        if commit_shas is not None:
            if not commit_shas:
                return []
            placeholders = ",".join("?" for _ in commit_shas)
            clauses += f" AND ce.commit_sha IN ({placeholders})"
            params.extend(sorted(commit_shas))
        if since is not None:
            clauses += (
                " AND COALESCE(datetime(ce.changed_at), ce.changed_at) "
                ">= COALESCE(datetime(?), ?)"
            )
            params.extend((since, since))
        if until is not None:
            clauses += (
                " AND COALESCE(datetime(ce.changed_at), ce.changed_at) "
                "<= COALESCE(datetime(?), ?)"
            )
            params.extend((until, until))
        rows = self.conn.execute(
            f"""
            SELECT ce.id AS change_event_id, ce.commit_sha, ce.path, ce.change_kind,
                   ce.actor, ce.changed_at,
                   ce.detected_branch, ce.detected_head_sha, ce.detected_at,
                   ce.detected_context,
                   ek.id AS entity_key_id, ek.locator, ek.sei
              FROM change_events ce
              JOIN entity_keys ek ON ek.id = ce.entity_key_id
             WHERE ce.repo_id = ?
             {clauses}
             ORDER BY COALESCE(datetime(ce.changed_at), ce.changed_at), ce.id
            """,
            params,
        ).fetchall()
        return [dict(row) for row in rows]

    def timeline(self, repo: Path, entity: str) -> list[dict[str, object]]:
        repo_id = self._repo_id(repo)
        rows = self.conn.execute(
            """
            SELECT ce.id AS change_event_id, ce.commit_sha, ce.path, ce.change_kind,
                   ce.actor, ce.changed_at,
                   ce.detected_branch, ce.detected_head_sha, ce.detected_at,
                   ce.detected_context,
                   ek.id AS entity_key_id, ek.locator, ek.sei
              FROM change_events ce
              JOIN entity_keys ek ON ek.id = ce.entity_key_id
             WHERE ce.repo_id = ?
               AND (ek.locator = ? OR ek.sei = ?)
             ORDER BY ce.changed_at, ce.id
            """,
            (repo_id, entity, entity),
        ).fetchall()
        return [dict(row) for row in rows]

    def entity_keys_by_ids(self, repo: Path, ids: list[int]) -> dict[int, dict[str, object]]:
        if not ids:
            return {}
        repo_id = self._repo_id(repo)
        placeholders = ",".join("?" for _ in ids)
        rows = self.conn.execute(
            f"""
            SELECT id, locator, sei FROM entity_keys
             WHERE repo_id = ? AND id IN ({placeholders})
            """,
            (repo_id, *ids),
        ).fetchall()
        return {int(row["id"]): dict(row) for row in rows}

    def resolve_ref(
        self, repo: Path, kind: str, value: object
    ) -> dict[str, object] | None:
        """Resolve a federation entity ref to a stored entity_key row, or None.

        Siblings key on ``sei`` (preferred) or ``locator``;
        ``warpline_entity_key_id`` is accepted for compatibility but is NOT a
        federation key.
        """

        repo_id = self._repo_id(repo)
        text = value if isinstance(value, str) else str(value)
        clause: str
        param: object
        if kind == "sei":
            clause, param = "ek.sei = ?", text
        elif kind == "locator":
            clause, param = "ek.locator = ?", text
        elif kind == "warpline_entity_key_id":
            if not isinstance(value, (int, str)):
                return None
            try:
                key_id = int(value)
            except (TypeError, ValueError):
                return None
            clause, param = "ek.id = ?", key_id
        else:  # auto | qualname | path — try sei then locator
            row = self.conn.execute(
                """
                SELECT id, locator, sei FROM entity_keys ek
                 WHERE repo_id = ? AND (ek.sei = ? OR ek.locator = ?)
                 ORDER BY (ek.sei = ?) DESC LIMIT 1
                """,
                (repo_id, text, text, text),
            ).fetchone()
            return dict(row) if row is not None else None
        row = self.conn.execute(
            f"SELECT id, locator, sei FROM entity_keys ek WHERE repo_id = ? AND {clause} LIMIT 1",
            (repo_id, param),
        ).fetchone()
        return dict(row) if row is not None else None

    def churn_for_entity(
        self,
        repo: Path,
        entity_key_id: int,
        commit_shas: set[str] | None = None,
        since: str | None = None,
        until: str | None = None,
    ) -> dict[str, object]:
        """Aggregate change_events for one entity (the GROUP-BY churn read)."""

        repo_id = self._repo_id(repo)
        clauses = ["repo_id = ?", "entity_key_id = ?"]
        params: list[object] = [repo_id, entity_key_id]
        if commit_shas is not None:
            if not commit_shas:
                return {"churn_count": 0, "first": None, "last": None, "last_actor": None}
            clauses.append(f"commit_sha IN ({','.join('?' for _ in commit_shas)})")
            params.extend(sorted(commit_shas))
        if since is not None:
            clauses.append("changed_at >= ?")
            params.append(since)
        if until is not None:
            clauses.append("changed_at <= ?")
            params.append(until)
        where = " AND ".join(clauses)
        row = self.conn.execute(
            f"""
            SELECT COUNT(*) AS churn_count,
                   MIN(changed_at) AS first_changed_at,
                   MAX(changed_at) AS last_changed_at
              FROM change_events WHERE {where}
            """,
            params,
        ).fetchone()
        count = int(row["churn_count"]) if row is not None else 0
        last_actor = None
        if count:
            actor_row = self.conn.execute(
                f"""
                SELECT actor FROM change_events WHERE {where}
                 ORDER BY changed_at DESC, id DESC LIMIT 1
                """,
                params,
            ).fetchone()
            last_actor = actor_row["actor"] if actor_row is not None else None
        return {
            "churn_count": count,
            "first": row["first_changed_at"] if row is not None else None,
            "last": row["last_changed_at"] if row is not None else None,
            "last_actor": last_actor,
        }

    def update_co_change_pairs(
        self,
        repo_id: str,
        commit_sha: str,
        entity_key_ids: set[int] | list[int],
        changed_at: str | None = None,
    ) -> dict[str, int | str]:
        """Upsert co-change pairs for one commit's changed entity set (Track A).

        Returns a small report dict: ``{"pairs": <written>, ...}``. Three honest
        early-return shapes carry their reason so the caller and tests can assert
        them without inspecting health_log:

        - kill-switch (B4): ``WARPLINE_COCHANGE`` set to a falsy/zero value →
          ``{"pairs": 0, "skipped": "kill_switch"}``; NO rows written, no health
          event. A pathological repo opts out without a code change.
        - high fan-out (R8/M7): more than ``_CO_CHANGE_FANOUT_CAP`` (30) changed
          entities in one commit → ``{"pairs": 0, "skipped": "high_fanout",
          "entities": <n>}``; records ``coupling_skipped=high_fanout`` via
          ``log_health`` (a count is also returned). High-fanout commits carry
          near-zero coupling signal, so generating O(n^2) pairs is pure noise.
        - too few entities (no pair possible) → ``{"pairs": 0}``.

        All writes are fail-soft: a SQLite error records ``coupling_write_failed``
        to health_log and returns ``{"pairs": 0, "error": ...}`` rather than
        propagating — co-change derivation NEVER blocks ingest.

        The ``>30`` cap is applied to the WHOLE commit's entity set (M7): the
        caller accumulates ids across the full path+locator loop and calls this
        ONCE per commit, so the cap is per-commit, not per-locator.
        """

        # B4 kill-switch: WARPLINE_COCHANGE set to "0"/"false"/"no"/"off" → skip.
        # An EMPTY string is NOT disabling (#6): empty and unset both mean
        # default-ON, so an explicitly-blank env var (e.g. ``WARPLINE_COCHANGE=``
        # exported in a shell rc) does not silently switch derivation off — only an
        # explicit falsy token does. Treating "" as a kill would be a false-precise
        # "user opted out" reading of what is really an absent choice.
        raw = os.environ.get("WARPLINE_COCHANGE")
        if raw is not None and raw.strip().lower() in {"0", "false", "no", "off"}:
            return {"pairs": 0, "skipped": "kill_switch"}

        ids = sorted(set(int(i) for i in entity_key_ids))
        n = len(ids)
        if n > _CO_CHANGE_FANOUT_CAP:
            # R8: record the skip both to health_log AND in the return dict.
            self.conn.execute(
                "INSERT INTO health_log(repo_id, code, message) VALUES (?, ?, ?)",
                (
                    repo_id,
                    "coupling_skipped",
                    f"high_fanout: {n} entities in commit {commit_sha} (cap "
                    f"{_CO_CHANGE_FANOUT_CAP})",
                ),
            )
            self.conn.commit()
            return {"pairs": 0, "skipped": "high_fanout", "entities": n}
        if n < 2:
            return {"pairs": 0}

        # Import locally to keep coupling.py a pure leaf (it never imports store,
        # avoiding an import cycle); store -> coupling is the one-way edge.
        from warpline.coupling import derive_pairs_from_commit

        pairs = derive_pairs_from_commit(ids)
        try:
            for key_a, key_b in pairs:
                self.conn.execute(
                    """
                    INSERT INTO co_change_pairs(
                      repo_id, entity_key_id_a, entity_key_id_b,
                      co_change_count, last_co_change, last_commit_sha
                    ) VALUES (?, ?, ?, 1, ?, ?)
                    ON CONFLICT(repo_id, entity_key_id_a, entity_key_id_b) DO UPDATE SET
                      co_change_count = co_change_count + 1,
                      -- #7 recency-marker guard: only ADVANCE the markers, and
                      -- never overwrite a populated timestamp with NULL. Live
                      -- ingest may arrive out of chronological order (e.g. a hook
                      -- for an older cherry-picked commit), and a co-change with a
                      -- NULL changed_at (pre-v2 backfill row) must not wipe a real
                      -- one. The guard: keep the existing marker unless the new
                      -- changed_at is non-null AND >= the stored one (a NULL stored
                      -- marker is always superseded by any non-null incoming).
                      last_commit_sha = CASE
                        WHEN excluded.last_co_change IS NOT NULL
                         AND (last_co_change IS NULL
                              OR excluded.last_co_change >= last_co_change)
                        THEN excluded.last_commit_sha
                        ELSE last_commit_sha
                      END,
                      last_co_change = CASE
                        WHEN excluded.last_co_change IS NOT NULL
                         AND (last_co_change IS NULL
                              OR excluded.last_co_change >= last_co_change)
                        THEN excluded.last_co_change
                        ELSE last_co_change
                      END
                    """,
                    (repo_id, key_a, key_b, changed_at, commit_sha),
                )
            self.conn.commit()
        except sqlite3.Error as exc:  # fail-soft: never block ingest (R8)
            self.conn.execute(
                "INSERT INTO health_log(repo_id, code, message) VALUES (?, ?, ?)",
                (repo_id, "coupling_write_failed", f"{commit_sha}: {exc}"),
            )
            self.conn.commit()
            return {"pairs": 0, "error": str(exc)}
        return {"pairs": len(pairs)}

    def co_change_partners(
        self,
        repo: Path,
        entity_key_id: int,
        min_count: int = 2,
    ) -> list[dict[str, object]]:
        """Co-change partners of one entity, with SEI joined at read time.

        Returns rows ordered by descending ``co_change_count``. Each row carries
        the partner's ``entity_key_id``, ``locator``, ``sei`` (NULL when the
        partner key was minted before its SEI resolved — honest ``sei:null``),
        ``co_change_count``, ``coupling_rate`` (suppressed to None below the
        sample floor), ``sample_size`` (the partner's total churn), and
        ``last_co_change``.

        Read-cost note: ``coupling_rate`` requires the partner's per-entity total
        churn, computed here with one COUNT per partner via ``churn_for_entity``.
        This is acceptable for the bounded partner lists this surface returns; if
        a hot path ever needs it at scale, denormalized totals are an additive
        later migration (no schema break).
        """

        repo_id = self._repo_id(repo)
        rows = self.conn.execute(
            """
            SELECT CASE WHEN entity_key_id_a = :id THEN entity_key_id_b
                        ELSE entity_key_id_a END AS partner_id,
                   co_change_count, last_co_change
              FROM co_change_pairs
             WHERE repo_id = :repo
               AND (entity_key_id_a = :id OR entity_key_id_b = :id)
               AND co_change_count >= :min_count
             ORDER BY co_change_count DESC, partner_id
            """,
            {"repo": repo_id, "id": int(entity_key_id), "min_count": int(min_count)},
        ).fetchall()

        from warpline.coupling import coupling_rate

        partners: list[dict[str, object]] = []
        for row in rows:
            partner_id = int(row["partner_id"])
            key = self.conn.execute(
                "SELECT locator, sei FROM entity_keys WHERE id = ? AND repo_id = ?",
                (partner_id, repo_id),
            ).fetchone()
            if key is None:
                continue
            total = int(str(self.churn_for_entity(repo, partner_id)["churn_count"]))
            co_count = int(row["co_change_count"])
            partners.append(
                {
                    "entity_key_id": partner_id,
                    "locator": key["locator"],
                    "sei": key["sei"],
                    "co_change_count": co_count,
                    "coupling_rate": coupling_rate(co_count, total),
                    "sample_size": total,
                    "last_co_change": row["last_co_change"],
                }
            )
        return partners

    def co_change_commit_groups(self, repo: Path) -> list[dict[str, object]]:
        """Group ``change_events`` by commit into ``(commit_sha, [entity_key_id])``.

        The rebuild input: one group per commit, deduplicated entity ids.
        ``last_co_change`` is the commit's max ``changed_at`` so a rebuilt row
        carries the same recency marker as the live ingest path.

        Ordering (#7): groups are yielded in CHRONOLOGICAL order
        (``MAX(changed_at)`` then ``commit_sha`` as a deterministic tie-break),
        NOT lexical commit-sha order. Live ingest advances the recency markers in
        the order commits actually arrive (≈ chronological), so a rebuild that
        replayed lexically would converge on the lexically-last commit's
        ``last_co_change``/``last_commit_sha`` instead of the chronologically
        latest — diverging from incremental. Replaying in changed_at order makes
        the two paths converge. The outer GROUP BY is per
        ``(commit_sha, entity_key_id)``; the window function gives every row of a
        commit that commit's max changed_at so the ORDER BY groups them together.
        """

        repo_id = self._repo_id(repo)
        rows = self.conn.execute(
            """
            SELECT commit_sha, entity_key_id, MAX(changed_at) AS changed_at,
                   MAX(changed_at) OVER (PARTITION BY commit_sha) AS commit_changed_at
              FROM change_events
             WHERE repo_id = ?
             GROUP BY commit_sha, entity_key_id
             ORDER BY commit_changed_at, commit_sha
            """,
            (repo_id,),
        ).fetchall()
        groups: dict[str, dict[str, object]] = {}
        for row in rows:
            sha = str(row["commit_sha"])
            group = groups.setdefault(
                sha, {"commit_sha": sha, "entity_key_ids": [], "changed_at": None}
            )
            ids = group["entity_key_ids"]
            assert isinstance(ids, list)
            ids.append(int(row["entity_key_id"]))
            changed = row["changed_at"]
            if changed is not None and (
                group["changed_at"] is None or str(changed) > str(group["changed_at"])
            ):
                group["changed_at"] = changed
        return list(groups.values())

    def clear_co_change_pairs(self, repo: Path) -> None:
        """Drop all co-change rows for a repo (rebuild precondition)."""

        repo_id = self._repo_id(repo)
        self.conn.execute("DELETE FROM co_change_pairs WHERE repo_id = ?", (repo_id,))
        self.conn.commit()

    def rebuild_co_change_pairs(self, repo: Path) -> dict[str, int]:
        """Rebuild the whole co-change graph from ``change_events`` (idempotent).

        Clears existing rows, then replays every commit group through the same
        ``update_co_change_pairs`` path the live ingest uses — so a rebuild and an
        incremental ingest converge to identical counts. Interruptible: each
        commit group commits independently; a re-run is idempotent because the
        clear precedes the replay.

        Returns ``{"commits": <groups replayed>, "pairs": <rows written>,
        "skipped": <high-fanout/kill-switch commits>}``.
        """

        repo_id = self.ensure_repo(repo)
        self.clear_co_change_pairs(repo)
        commits = 0
        pairs = 0
        skipped = 0
        for group in self.co_change_commit_groups(repo):
            ids = group["entity_key_ids"]
            assert isinstance(ids, list)
            report = self.update_co_change_pairs(
                repo_id,
                str(group["commit_sha"]),
                ids,
                changed_at=(
                    None if group["changed_at"] is None else str(group["changed_at"])
                ),
            )
            commits += 1
            written = report.get("pairs", 0)
            pairs += int(written) if isinstance(written, int) else 0
            if report.get("skipped"):
                skipped += 1
        return {"commits": commits, "pairs": pairs, "skipped": skipped}

    def log_health(self, repo: Path, code: str, message: str) -> None:
        repo_id = self.ensure_repo(repo)
        self.conn.execute(
            "INSERT INTO health_log(repo_id, code, message) VALUES (?, ?, ?)",
            (repo_id, code, message),
        )
        self.conn.commit()

    def create_edge_snapshot(
        self,
        repo_id: str,
        commit_sha: str,
        source: str,
        source_version: str,
        completeness: str,
    ) -> int:
        if completeness not in {"FULL", "DELTA", "SKIPPED"}:
            raise ValueError(f"invalid snapshot completeness: {completeness}")
        cur = self.conn.execute(
            """
            INSERT INTO edge_snapshots(repo_id, commit_sha, source, source_version, completeness)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(repo_id, commit_sha, source) DO UPDATE SET
              source_version = excluded.source_version,
              completeness = excluded.completeness,
              captured_at = CURRENT_TIMESTAMP
            RETURNING id
            """,
            (repo_id, commit_sha, source, source_version, completeness),
        )
        row = cur.fetchone()
        self.conn.commit()
        if row is None:
            raise RuntimeError("failed to create edge snapshot")
        return int(row["id"])

    def append_snapshot_edge(
        self,
        snapshot_id: int,
        *,
        source_entity_key_id: int,
        target_entity_key_id: int,
        edge_kind: str,
        confidence: str,
    ) -> None:
        self.append_snapshot_edges(
            snapshot_id,
            [(source_entity_key_id, target_entity_key_id, edge_kind, confidence)],
        )

    def append_snapshot_edges(
        self,
        snapshot_id: int,
        edges: Iterable[tuple[int, int, str, str]],
    ) -> None:
        rows = [
            (snapshot_id, source_entity_key_id, target_entity_key_id, edge_kind, confidence)
            for source_entity_key_id, target_entity_key_id, edge_kind, confidence in edges
        ]
        if not rows:
            return
        self.conn.executemany(
            """
            INSERT OR IGNORE INTO snapshot_edges(
              snapshot_id, source_entity_key_id, target_entity_key_id, edge_kind, confidence
            ) VALUES (?, ?, ?, ?, ?)
            """,
            rows,
        )
        self.conn.commit()

    def clear_snapshot_edges(self, snapshot_id: int) -> None:
        self.conn.execute("DELETE FROM snapshot_edges WHERE snapshot_id = ?", (snapshot_id,))
        self.conn.commit()

    def capture_snapshot_atomic(
        self,
        *,
        repo_id: str,
        commit_sha: str,
        source: str,
        source_version: str,
        completeness: str,
        edges: list[tuple[int, int, str, str]],
    ) -> int:
        """Capture a snapshot correct-by-construction in ONE transaction.

        Precondition: callers must not hold an open implicit transaction on
        ``self.conn`` — every preceding DML (e.g. ``ensure_entity_key``) must
        already be committed before this method is called.

        Upserts the ``edge_snapshots`` row, replaces its edges, and sets the
        final ``completeness`` inside a single ``BEGIN IMMEDIATE``..``COMMIT``.
        No intermediate COMMIT is issued, so a reader on another connection (WAL)
        can never observe a half-written state, and any exception ROLLBACKs the
        whole transaction — leaving the PRIOR committed snapshot intact (R3 /
        fail-closed). ``edges`` is fully staged by the caller before this opens;
        no Loomweave I/O or completeness decision happens inside the txn.

        Mirrors the explicit-transaction convention at
        ``reresolve_entity_key_sei`` (no reliance on autocommit, no nested
        per-statement commits).
        """
        if completeness not in {"FULL", "DELTA", "SKIPPED"}:
            raise ValueError(f"invalid snapshot completeness: {completeness}")
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            cur = self.conn.execute(
                """
                INSERT INTO edge_snapshots(
                  repo_id, commit_sha, source, source_version, completeness
                )
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(repo_id, commit_sha, source) DO UPDATE SET
                  source_version = excluded.source_version,
                  completeness = excluded.completeness,
                  captured_at = CURRENT_TIMESTAMP
                RETURNING id
                """,
                (repo_id, commit_sha, source, source_version, completeness),
            )
            row = cur.fetchone()
            if row is None:
                raise RuntimeError("failed to create edge snapshot")
            snapshot_id = int(row["id"])
            # Replace edges wholesale: a re-capture for the same (repo, commit,
            # source) is a fresh edge set, not an append.
            self.conn.execute(
                "DELETE FROM snapshot_edges WHERE snapshot_id = ?", (snapshot_id,)
            )
            if edges:
                self.conn.executemany(
                    """
                    INSERT OR IGNORE INTO snapshot_edges(
                      snapshot_id, source_entity_key_id, target_entity_key_id, edge_kind, confidence
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    [
                        (snapshot_id, source_id, target_id, edge_kind, confidence)
                        for source_id, target_id, edge_kind, confidence in edges
                    ],
                )
            self.conn.execute("COMMIT")
            return snapshot_id
        except BaseException:
            self.conn.execute("ROLLBACK")
            raise

    def latest_snapshot(self, repo: Path) -> dict[str, object] | None:
        repo_id = self._repo_id(repo)
        row = self.conn.execute(
            """
            SELECT id, commit_sha, source, source_version, captured_at, completeness
              FROM edge_snapshots
             WHERE repo_id = ?
             ORDER BY id DESC
             LIMIT 1
            """,
            (repo_id,),
        ).fetchone()
        return dict(row) if row is not None else None

    def snapshot_edges(self, snapshot_id: int) -> list[dict[str, object]]:
        rows = self.conn.execute(
            """
            SELECT source_entity_key_id, target_entity_key_id, edge_kind, confidence
              FROM snapshot_edges
             WHERE snapshot_id = ?
            """,
            (snapshot_id,),
        ).fetchall()
        return [dict(row) for row in rows]
