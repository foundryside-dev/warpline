from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path
from types import TracebackType

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


def default_store_path(repo: Path, base_dir: Path | None = None) -> Path:
    root = repo.resolve()
    state = base_dir or root / ".weft" / "heddle"
    return state / "heddle.db"


class HeddleStore:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    @classmethod
    def open(cls, path: Path) -> HeddleStore:
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        conn.executescript(SCHEMA)
        return cls(conn)

    def __enter__(self) -> HeddleStore:
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
    ) -> None:
        self.conn.execute(
            """
            INSERT OR IGNORE INTO change_events(
              repo_id, entity_key_id, commit_sha, path, change_kind,
              actor, changed_at, hunk_summary
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
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
            ),
        )
        self.conn.commit()

    def list_change_events(
        self, repo: Path, commit_shas: set[str] | None = None
    ) -> list[dict[str, object]]:
        repo_id = self._repo_id(repo)
        params: list[object] = [repo_id]
        commit_filter = ""
        if commit_shas is not None:
            if not commit_shas:
                return []
            placeholders = ",".join("?" for _ in commit_shas)
            commit_filter = f" AND ce.commit_sha IN ({placeholders})"
            params.extend(sorted(commit_shas))
        rows = self.conn.execute(
            f"""
            SELECT ce.commit_sha, ce.path, ce.change_kind, ce.actor, ce.changed_at,
                   ek.id AS entity_key_id, ek.locator, ek.sei
              FROM change_events ce
              JOIN entity_keys ek ON ek.id = ce.entity_key_id
             WHERE ce.repo_id = ?
             {commit_filter}
             ORDER BY ce.changed_at, ce.id
            """,
            params,
        ).fetchall()
        return [dict(row) for row in rows]

    def timeline(self, repo: Path, entity: str) -> list[dict[str, object]]:
        repo_id = self._repo_id(repo)
        rows = self.conn.execute(
            """
            SELECT ce.commit_sha, ce.path, ce.change_kind, ce.actor, ce.changed_at,
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
        self.conn.execute(
            """
            INSERT OR IGNORE INTO snapshot_edges(
              snapshot_id, source_entity_key_id, target_entity_key_id, edge_kind, confidence
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (snapshot_id, source_entity_key_id, target_entity_key_id, edge_kind, confidence),
        )
        self.conn.commit()

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
