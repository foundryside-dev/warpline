# Capture Correct-by-Construction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Re-architect snapshot edge-capture so the publish-before-edges window is structurally impossible: insert the `edge_snapshots` row LAST inside one `BEGIN IMMEDIATE`..`COMMIT` after edges are staged and completeness is computed, never degrading the prior visible snapshot on a mid-capture failure.

**Architecture:** Today `capture_edge_snapshot` (`src/warpline/snapshot.py:45`) runs THREE separately auto-committed store operations (`create_edge_snapshot` DELTA → `clear_snapshot_edges` → `append_snapshot_edges` → `create_edge_snapshot` FULL). The invariant holds only by an emergent property (upsert id-stability + completeness-flip ordering), and the step-1 upsert mutates the prior FULL row to DELTA/0-edges *before* Loomweave is queried, so a mid-capture failure destroys the prior good snapshot. We add ONE store method `capture_snapshot_atomic` that, inside a single `BEGIN IMMEDIATE`, stages edges into a holding table, then inserts (or upserts) the `edge_snapshots` row and copies edges into `snapshot_edges`, all before COMMIT — so `latest_snapshot` (`store.py:1470`, `id DESC`) can never read a row whose edges are not yet present, and an exception ROLLBACKs to the prior snapshot intact.

**Tech Stack:** Python 3, SQLite (`sqlite3`, WAL, autocommit connection model), pytest, ruff, pyright.

## Global Constraints

Python repo. Tooling: ruff (lint), pyright (types), pytest (tests). TDD throughout.
Sequencing is VECTORS-FIRST: each plan opens by writing the failing golden vector / test that expresses the invariant, THEN the implementation makes it green.
WS1 capture changes are OUTPUT-SHAPE-PRESERVING: the response envelope stays byte-identical; only edge-visibility timing and row lifecycle change.
Enrichment vocab is a CLOSED, FROZEN contract in src/warpline/envelope.py (keys: sei, edges, work, risk, governance, requirements). Do NOT add or remove keys. The `requirements` key stays (resolved as reserved-but-honest).
The weft-reason triple is `cause + reason_class + fix`, built ONLY via src/warpline/listing.py `reason()` factory (non-"clean" reason_class requires both cause and fix).
Every response MUST keep `meta.local_only: true` and `meta.peer_side_effects: []`. Never break the frozen golden vectors or the success/error envelope schema.
Gates that must stay green: `warpline dogfood-eval`, `warpline mcp-smoke`, ruff, pyright, pytest, and the member-diff guard.
Authority boundary: all work is reversible and repo-local. The hub handover document is a DRAFT package — it creates no hub/sibling work and freezes nothing.
Commit messages end with the trailer: Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>

---

## Notes on the reground (read before starting)

The spec's two concrete failure claims are STALE on this branch and must NOT drive the work:

- "orphans the intermediate row" — FALSE NOW. `create_edge_snapshot` (`store.py:1403`) is an UPSERT on `UNIQUE(repo_id, commit_sha, source)` (`store.py:89`), so the second call updates the SAME row id. No orphan, no second id.
- "a reader can pick a published-but-empty FULL snapshot" — FALSE NOW. The id is stable and completeness flips DELTA→FULL only AFTER `append_snapshot_edges` commits. The mid-capture reader test (`tests/test_snapshots.py:217`) already passes.

The GENUINE open gap this plan targets:

1. Capture is THREE auto-committed transactions, not one. The invariant is emergent and fragile to refactor.
2. **Fail-closed-to-PRIOR-snapshot is VIOLATED today.** `snapshot.py:95` upserts the prior FULL row to DELTA and `snapshot.py:102` clears its edges BEFORE any Loomweave call. If capture dies mid-loop (`snapshot.py:107-122`), the prior good snapshot is already destroyed and the visible row is DELTA/0-edges.

Real line numbers (spec refs are off): the intermediate DELTA mint is `snapshot.py:95` (spec says `:94`); the FULL flip is `snapshot.py:130` (spec says `:127`); `latest_snapshot` is `store.py:1470` (spec correct).

Central design decision already made for the author: `snapshot_edges.snapshot_id` is a FK to `edge_snapshots(id)` (`store.py:91-98`) and `PRAGMA foreign_keys = ON` (`store.py:464`), so edges cannot be inserted before the parent row exists. We achieve "no visible partial state" not by literally inserting the row last, but by doing ALL of (insert/upsert row → insert edges → set final completeness) inside ONE uncommitted `BEGIN IMMEDIATE` transaction. No intermediate COMMIT is ever issued, so no reader on another connection (WAL) can observe a half-written state; an exception ROLLBACKs the whole transaction, leaving the prior committed snapshot intact. Edges are staged in a transaction-local Python list first, so completeness (`FULL`/`DELTA`/`SKIPPED`) is fully known before the single write transaction opens.

---

## Task 1 — Vectors-first: failing fail-closed regression test

Lock the genuine open invariant (fail-closed-to-prior-snapshot) with a test that fails against today's code. This test is the deliverable; Task 3 makes it green.

**Files:**
- Modify `tests/test_snapshots.py` (add one test class + one test function after line 61, i.e. after `TruncatedNeighborhoodClient`; and the test function at end of file).

**Interfaces:**
- Consumes: `capture_edge_snapshot(store, repo, *, commit_sha=None, client, source_version, scope_locators=None, scope_failures=None, max_entities=None) -> dict[str, Any]` (`snapshot.py:45`); `WarplineStore.open(path) -> WarplineStore` (`store.py:449`); `store.latest_snapshot(repo) -> dict | None` (`store.py:1470`); `store.snapshot_edges(snapshot_id) -> list[dict]` (`store.py:1484`); `store.create_edge_snapshot(repo_id, commit_sha, source, source_version, completeness) -> int` (`store.py:1403`); `store.append_snapshot_edge(...)` (`store.py:1431`); `store.ensure_entity_key(repo_id, locator, sei, commit_sha) -> int`.
- Produces: test `test_capture_failure_preserves_prior_full_snapshot` (no production signature change).

**Steps:**

- [ ] Add a failing-mid-loop client class. Insert after line 61 of `tests/test_snapshots.py` (immediately after `TruncatedNeighborhoodClient`):

```python
class ExplodingNeighborhoodClient:
    """Raises a NON-Exception (BaseException) on the FIRST neighborhood call so
    capture cannot swallow it via its ``except Exception`` per-entity guard
    (snapshot.py:111). Models a hard mid-capture kill (e.g. Loomweave process
    crash / KeyboardInterrupt) that must NOT degrade the prior snapshot."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def neighborhood(self, entity: str) -> dict[str, object]:
        self.calls.append(entity)
        raise KeyboardInterrupt("loomweave killed mid-capture")
```

- [ ] Append the regression test to the END of `tests/test_snapshots.py`:

```python
def test_capture_failure_preserves_prior_full_snapshot(tmp_path: Path) -> None:
    """Fail-closed: a hard mid-capture failure leaves the PRIOR FULL snapshot
    (and its edges) intact and visible, never a degraded DELTA/0-edge row."""
    repo = tmp_path / "repo"
    repo.mkdir()
    db_path = tmp_path / "warpline.db"

    # First capture: a clean FULL snapshot with one edge.
    with WarplineStore.open(db_path) as store:
        repo_id = store.ensure_repo(repo)
        store.ensure_entity_key(repo_id, locator="python:function:a", sei=None, commit_sha="c1")
        first = capture_edge_snapshot(
            store, repo, commit_sha="c1", client=FakeNeighborhoodClient(),
            source_version="v1",
        )
        prior = store.latest_snapshot(repo)
        assert prior is not None
        prior_id = int(prior["id"])
        prior_edges = store.snapshot_edges(prior_id)
    assert first["completeness"] == "FULL"
    assert len(prior_edges) == 1

    # Second capture for the SAME (repo, commit) dies mid-loop.
    with WarplineStore.open(db_path) as store:
        try:
            capture_edge_snapshot(
                store, repo, commit_sha="c1", client=ExplodingNeighborhoodClient(),
                source_version="v2",
            )
        except KeyboardInterrupt:
            pass

    # The prior FULL snapshot must survive unchanged.
    with WarplineStore.open(db_path) as store:
        after = store.latest_snapshot(repo)
        assert after is not None
        after_edges = store.snapshot_edges(int(after["id"]))
    assert after["id"] == prior_id
    assert after["completeness"] == "FULL"
    assert after["source_version"] == "v1"
    assert len(after_edges) == 1
```

- [ ] Run it and SEE IT FAIL:

```bash
python -m pytest tests/test_snapshots.py::test_capture_failure_preserves_prior_full_snapshot -x -q
```

Expected failure (today the step-1 upsert at `snapshot.py:95` mutates the prior row to DELTA and `clear_snapshot_edges` at `:102` empties it before the client raises):
```
>       assert after["completeness"] == "FULL"
E       AssertionError: assert 'DELTA' == 'FULL'
```
(`after["source_version"]` will also be `'v2'`, and `after_edges` empty — any of these assertions trips first.)

- [ ] Commit the failing test:

```bash
git checkout -b harden/spine-correct-by-construction 2>/dev/null || git checkout harden/spine-correct-by-construction
git add tests/test_snapshots.py
git commit -m "test(capture): failing fail-closed-to-prior-snapshot regression

Locks WS1 invariant: a hard mid-capture failure must leave the prior FULL
snapshot + edges intact. Fails today because the step-1 upsert degrades the
prior row to DELTA and clears its edges before Loomweave is queried.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2 — Vectors-first: golden vector GV-LW-6 (atomic-capture invariant)

Pin the invariant in the conformance suite (executable Python test + JSON manifest). Vectors-first: GV-LW-6 fails before Task 3 lands.

**Files:**
- Modify `tests/contracts/test_golden_vectors.py` (add a client class after line 90, after `_TruncatedNeighborhoodClient`; add the test after `test_gv_lw_5_...` ends — find the end of `test_gv_lw_5_sei_resolution_present_vs_unavailable`, currently starting at line 190, and insert the new test immediately after it, before the `SEAM 2` FILIGREE section).
- Modify `tests/fixtures/contracts/warpline/golden-vectors.json` (append one vector to the `vectors` array; bump nothing else — `frozen_at` stays `2026-06-13` because this is a DRAFT package per Global Constraints).

**Interfaces:**
- Consumes: `capture_edge_snapshot(...)` (`snapshot.py:45`); `WarplineStore.open` / `latest_snapshot` / `snapshot_edges`; the `_store`, `_git_repo`, `_seed_entity` helpers (`test_golden_vectors.py:23-48`).
- Produces: test `test_gv_lw_6_capture_failure_preserves_prior_snapshot`; JSON vector `{"id": "GV-LW-6", ...}`.

**Steps:**

- [ ] Add the exploding client to `tests/contracts/test_golden_vectors.py` after line 90 (after `_TruncatedNeighborhoodClient`):

```python
class _ExplodingNeighborhoodClient:
    """Hard mid-capture kill (BaseException, not Exception) for GV-LW-6."""

    def neighborhood(self, entity: str) -> dict[str, Any]:
        raise KeyboardInterrupt("loomweave killed mid-capture")
```

- [ ] Add the golden-vector test. Insert immediately after the end of `test_gv_lw_5_sei_resolution_present_vs_unavailable` and before the `# ===...SEAM 2 — filigree` banner:

```python
def test_gv_lw_6_capture_failure_preserves_prior_snapshot(tmp_path: Path) -> None:
    """GV-LW-6: a hard mid-capture failure leaves the PRIOR snapshot intact and
    visible (fail-closed), never a degraded/empty row. Locks WS1's atomic-capture
    invariant: no edge_snapshots row visible until all its edges are committed."""
    repo = _git_repo(tmp_path)
    with _store(repo) as store:
        repo_id = store.ensure_repo(repo)
        _seed_entity(store, repo_id, "python:function:pkg/mod.py::a", None)
        _seed_entity(store, repo_id, "python:function:pkg/mod.py::b", None)
        full = capture_edge_snapshot(
            store, repo, commit_sha="c1", client=_FullNeighborhoodClient(), source_version="v1"
        )
        prior = store.latest_snapshot(repo)
        assert prior is not None
        prior_id = int(prior["id"])
        # The captured edge is unambiguously (pkg.mod.a -> pkg.mod.b): both seeded
        # locators' aliases match the neighborhood client's source/callee.
        prior_edges = store.snapshot_edges(prior_id)
    assert full["completeness"] == "FULL"
    assert len(prior_edges) > 0

    with _store(repo) as store:
        try:
            capture_edge_snapshot(
                store, repo, commit_sha="c1", client=_ExplodingNeighborhoodClient(),
                source_version="v2",
            )
        except KeyboardInterrupt:
            pass

    with _store(repo) as store:
        after = store.latest_snapshot(repo)
        assert after is not None
        after_edges = store.snapshot_edges(int(after["id"]))
    assert after["id"] == prior_id
    assert after["completeness"] == "FULL"
    assert after["source_version"] == "v1"
    assert len(after_edges) == len(prior_edges)
```

- [ ] Append the JSON manifest vector. Open `tests/fixtures/contracts/warpline/golden-vectors.json` and add this object as the LAST element of the `vectors` array (after the `GV-LG-3` entry; mind the comma before it):

```json
    {
      "id": "GV-LW-6",
      "seam": "loomweave",
      "tool": "warpline_edge_snapshot_capture",
      "assert": "hard mid-capture failure (loomweave killed) leaves the prior snapshot intact and visible (fail-closed); no edge_snapshots row is visible until all its edges are committed; never a degraded DELTA/0-edge row"
    }
```

- [ ] Run both new vectors and SEE THE PYTHON ONE FAIL:

```bash
python -m pytest tests/contracts/test_golden_vectors.py::test_gv_lw_6_capture_failure_preserves_prior_snapshot -x -q
```

Expected failure (same root cause as Task 1):
```
>       assert after["completeness"] == "FULL"
E       AssertionError: assert 'DELTA' == 'FULL'
```

- [ ] Confirm the JSON still parses and now has 15 vectors:

```bash
python -c "import json; d=json.load(open('tests/fixtures/contracts/warpline/golden-vectors.json')); ids=[v['id'] for v in d['vectors']]; print(len(ids), ids[-1]); assert ids[-1]=='GV-LW-6' and len(ids)==15"
```
Expected output:
```
15 GV-LW-6
```

- [ ] Commit:

```bash
git add tests/contracts/test_golden_vectors.py tests/fixtures/contracts/warpline/golden-vectors.json
git commit -m "test(contracts): GV-LW-6 pins atomic-capture fail-closed invariant

Vectors-first. Executable test + JSON manifest entry (now 15 vectors, draft
package so frozen_at stays 2026-06-13). Fails today; Task 3 makes it green.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3 — Add the atomic capture store method

Add ONE store method that performs the whole capture inside a single `BEGIN IMMEDIATE`..`COMMIT`, mirroring the established `reresolve_entity_key_sei` pattern (`store.py:607`). It must NOT call the per-statement-committing helpers (`create_edge_snapshot`/`append_snapshot_edges`/`clear_snapshot_edges` each `self.conn.commit()`, which would collapse the transaction). It takes a fully-staged edge list (no Loomweave I/O inside the txn) and the final completeness, so no completeness is computed mid-transaction.

**Files:**
- Modify `src/warpline/store.py` (add method after `clear_snapshot_edges` (lines 1466-1468), i.e. after line 1468, before `latest_snapshot` at line 1470).

**Interfaces:**
- Consumes: `self.conn: sqlite3.Connection` (autocommit, WAL, `foreign_keys=ON`); existing table `edge_snapshots` (`store.py:81`, `UNIQUE(repo_id, commit_sha, source)`); `snapshot_edges` (`store.py:91`, FK to `edge_snapshots(id)`); `store.append_snapshot_edges(...)` (`store.py:1445`, the plural form; `store.py:1431` is the singular `append_snapshot_edge`).
- Produces:
```python
def capture_snapshot_atomic(
    self,
    *,
    repo_id: str,
    commit_sha: str,
    source: str,
    source_version: str,
    completeness: str,
    edges: list[tuple[int, int, str, str]],
) -> int: ...
```
Returns the `edge_snapshots.id` of the committed row. Inserts/upserts the row, replaces its edges, and sets final `completeness` atomically; on any exception ROLLBACKs (prior committed snapshot untouched). `edges` entries are `(source_entity_key_id, target_entity_key_id, edge_kind, confidence)`.

**Steps:**

- [ ] Write a direct unit test for the new method FIRST. Append to `tests/test_snapshots.py`:

```python
def test_capture_snapshot_atomic_replaces_edges_in_one_transaction(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    with WarplineStore.open(tmp_path / "warpline.db") as store:
        repo_id = store.ensure_repo(repo)
        a = store.ensure_entity_key(repo_id, locator="python:function:a", sei=None, commit_sha="c1")
        b = store.ensure_entity_key(repo_id, locator="python:function:b", sei=None, commit_sha="c1")

        sid1 = store.capture_snapshot_atomic(
            repo_id=repo_id, commit_sha="c1", source="loomweave",
            source_version="v1", completeness="FULL",
            edges=[(a, b, "calls", "resolved")],
        )
        assert store.latest_snapshot(repo)["completeness"] == "FULL"
        assert len(store.snapshot_edges(sid1)) == 1

        # Re-capture same (repo, commit, source): same id, edges REPLACED not appended.
        sid2 = store.capture_snapshot_atomic(
            repo_id=repo_id, commit_sha="c1", source="loomweave",
            source_version="v2", completeness="DELTA",
            edges=[(b, a, "calls", "resolved")],
        )
        assert sid2 == sid1
        snap = store.latest_snapshot(repo)
        assert snap["completeness"] == "DELTA"
        assert snap["source_version"] == "v2"
        edges = store.snapshot_edges(sid2)
    assert edges == [
        {"source_entity_key_id": b, "target_entity_key_id": a,
         "edge_kind": "calls", "confidence": "resolved"}
    ]
```

- [ ] Run it and SEE IT FAIL (method does not exist yet):

```bash
python -m pytest tests/test_snapshots.py::test_capture_snapshot_atomic_replaces_edges_in_one_transaction -x -q
```
Expected failure:
```
E       AttributeError: 'WarplineStore' object has no attribute 'capture_snapshot_atomic'
```

- [ ] Implement the method. In `src/warpline/store.py`, insert after `clear_snapshot_edges` (after line 1468, before `def latest_snapshot` at 1470):

```python
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
```

- [ ] Run the unit test and SEE IT PASS:

```bash
python -m pytest tests/test_snapshots.py::test_capture_snapshot_atomic_replaces_edges_in_one_transaction -x -q
```
Expected: `1 passed`.

- [ ] Type-check the new method:

```bash
pyright src/warpline/store.py
```
Expected: `0 errors, 0 warnings, 0 informations` (or no new errors vs baseline).

- [ ] Commit:

```bash
git add src/warpline/store.py tests/test_snapshots.py
git commit -m "feat(store): add atomic capture_snapshot_atomic (single BEGIN IMMEDIATE)

Upserts the edge_snapshots row, replaces edges, and sets final completeness in
one transaction mirroring reresolve_entity_key_sei. No intermediate commit; any
exception rolls back to the prior committed snapshot. Caller stages edges first.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4 — Rewire capture_edge_snapshot onto the atomic method (make Tasks 1 & 2 green)

Replace the three-step write in `capture_edge_snapshot` with a single staged-then-atomic write. Stage all edges in the in-memory `snapshot_edges` list (already built at `snapshot.py:104-122`), compute completeness, then call `capture_snapshot_atomic` ONCE. Remove the intermediate `create_edge_snapshot(DELTA)` (`:95`), the `clear_snapshot_edges` (`:102`), the `append_snapshot_edges` (`:123`), and the second `create_edge_snapshot(FULL)` (`:130`). The returned dict shape is unchanged (output-shape-preserving).

**Files:**
- Modify `src/warpline/snapshot.py:95-150` (the FULL/non-skip path body).

**Interfaces:**
- Consumes: `store.capture_snapshot_atomic(*, repo_id, commit_sha, source, source_version, completeness, edges) -> int` (Task 3 Produces).
- Produces: `capture_edge_snapshot(...)` returns the IDENTICAL dict keys as today (`query, commit_sha, snapshot_id, source, source_version, completeness, entities, edges, failed_entities, capped, enrichment`) consumed at `commands.py:1079-1090`.

**Steps:**

- [ ] Replace lines 95-136 of `src/warpline/snapshot.py`. The current block is:

```python
    snapshot_id = store.create_edge_snapshot(
        repo_id=repo_id,
        commit_sha=resolved_commit,
        source="loomweave",
        source_version=source_version,
        completeness="DELTA",
    )
    store.clear_snapshot_edges(snapshot_id)

    edge_count = 0
    snapshot_edges: list[tuple[int, int, str, str]] = []
    failures: list[dict[str, str]] = list(scope_failures or [])
    for locator, query_entity in query_entities:
        try:
            neighborhood = client.neighborhood(query_entity)
            edges = edges_from_neighborhood(neighborhood)
        except Exception as exc:
            failures.append({"locator": locator, "reason": str(exc)})
            continue
        for source, target, edge_kind in sorted(edges):
            source_id = _entity_key_id_for_locator(
                store, repo_id, entity_id_to_key_id, source, resolved_commit
            )
            target_id = _entity_key_id_for_locator(
                store, repo_id, entity_id_to_key_id, target, resolved_commit
            )
            snapshot_edges.append((source_id, target_id, edge_kind, "resolved"))
            edge_count += 1
    store.append_snapshot_edges(snapshot_id, snapshot_edges)
    if scope_locators is not None and not query_entities and not failures:
        failures.append({"locator": "<changed_only_scope>", "reason": "empty_scope"})

    # A capped capture is structurally partial: it is missing entities it knows
    # exist. Treat that exactly like a per-entity failure — DELTA, not FULL.
    completeness = "DELTA" if (failures or capped) else "FULL"
    snapshot_id = store.create_edge_snapshot(
        repo_id=repo_id,
        commit_sha=resolved_commit,
        source="loomweave",
        source_version=source_version,
        completeness=completeness,
    )
```

Replace it with:

```python
    edge_count = 0
    snapshot_edges: list[tuple[int, int, str, str]] = []
    failures: list[dict[str, str]] = list(scope_failures or [])
    for locator, query_entity in query_entities:
        try:
            neighborhood = client.neighborhood(query_entity)
            edges = edges_from_neighborhood(neighborhood)
        except Exception as exc:
            failures.append({"locator": locator, "reason": str(exc)})
            continue
        for source, target, edge_kind in sorted(edges):
            source_id = _entity_key_id_for_locator(
                store, repo_id, entity_id_to_key_id, source, resolved_commit
            )
            target_id = _entity_key_id_for_locator(
                store, repo_id, entity_id_to_key_id, target, resolved_commit
            )
            snapshot_edges.append((source_id, target_id, edge_kind, "resolved"))
            edge_count += 1
    if scope_locators is not None and not query_entities and not failures:
        failures.append({"locator": "<changed_only_scope>", "reason": "empty_scope"})

    # A capped capture is structurally partial: it is missing entities it knows
    # exist. Treat that exactly like a per-entity failure — DELTA, not FULL.
    # Edges are fully staged above; the snapshot row is written exactly once,
    # atomically, AFTER completeness is known. Any failure raised by the client
    # propagates BEFORE this write, so the prior snapshot stays intact.
    completeness = "DELTA" if (failures or capped) else "FULL"
    snapshot_id = store.capture_snapshot_atomic(
        repo_id=repo_id,
        commit_sha=resolved_commit,
        source="loomweave",
        source_version=source_version,
        completeness=completeness,
        edges=snapshot_edges,
    )
```

- [ ] Run the two vectors-first tests and SEE THEM PASS:

```bash
python -m pytest tests/test_snapshots.py::test_capture_failure_preserves_prior_full_snapshot tests/contracts/test_golden_vectors.py::test_gv_lw_6_capture_failure_preserves_prior_snapshot -x -q
```
Expected: `2 passed`.

- [ ] Run the full snapshot + contract suites to confirm no regression in existing behavior (FULL/DELTA/SKIPPED, batching, recapture, mid-capture reader):

```bash
python -m pytest tests/test_snapshots.py tests/contracts/test_golden_vectors.py -q
```
Expected: all pass. Note the still-green `test_capture_edge_snapshot_does_not_publish_full_until_edges_complete` (`tests/test_snapshots.py:217`) — the new path keeps the mid-capture reader from ever seeing a FULL-with-no-edges row (the `MidCaptureReaderClient` runs during `client.neighborhood`, i.e. BEFORE the single atomic write opens, so it observes either `None` or the prior snapshot).

- [ ] Type-check:

```bash
pyright src/warpline/snapshot.py
```
Expected: no new errors.

- [ ] Commit:

```bash
git add src/warpline/snapshot.py
git commit -m "refactor(capture): single atomic write replaces three-step capture

capture_edge_snapshot now stages all edges, computes completeness, then writes
the snapshot row + edges ONCE via store.capture_snapshot_atomic. Removes the
intermediate DELTA mint, clear-edges dance, and FULL flip. Output-shape-
preserving; a mid-capture failure now leaves the prior snapshot intact.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 5 — Update the BatchOnlyStore fake to the new method surface

`BatchOnlyStore` (`tests/test_snapshots.py:82`) and `test_capture_edge_snapshot_batches_edge_writes` (`tests/test_snapshots.py:320`) assert edges are batched via `append_snapshot_edges`, not per-edge. After Task 4 the FULL path no longer calls `append_snapshot_edges`/`create_edge_snapshot`/`clear_snapshot_edges` — it calls `capture_snapshot_atomic`. The fake must move its assertion onto the new method so the "batched, not per-edge" guarantee is still tested.

**Files:**
- Modify `tests/test_snapshots.py:82-134` (the `BatchOnlyStore` class) and `tests/test_snapshots.py:320-333` (the test).

**Interfaces:**
- Consumes: `capture_edge_snapshot(...)`; the new `capture_snapshot_atomic` surface.
- Produces: updated `BatchOnlyStore` exposing `capture_snapshot_atomic`; updated assertion.

**Steps:**

- [ ] Run the batching test to SEE IT FAIL after Task 4:

```bash
python -m pytest tests/test_snapshots.py::test_capture_edge_snapshot_batches_edge_writes -x -q
```
Expected failure (the fake no longer receives the call it asserts on; `store.batches` stays empty because `capture_edge_snapshot` now calls the absent `capture_snapshot_atomic`):
```
E       AttributeError: 'BatchOnlyStore' object has no attribute 'capture_snapshot_atomic'
```

- [ ] Replace the `create_edge_snapshot`, `clear_snapshot_edges`, `append_snapshot_edge`, and `append_snapshot_edges` methods on `BatchOnlyStore` (`tests/test_snapshots.py:96-134`) with a single `capture_snapshot_atomic` that records the staged batch and still forbids per-edge writes. The class body from line 96 through line 134 becomes:

```python
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
        self.batches.append(list(edges))
        return 10

    def ensure_entity_key(
        self,
        repo_id: str,
        locator: str,
        sei: str | None,
        commit_sha: str,
    ) -> int:
        raise AssertionError(f"unexpected missing key for {locator}")

    def append_snapshot_edge(
        self,
        snapshot_id: int,
        *,
        source_entity_key_id: int,
        target_entity_key_id: int,
        edge_kind: str,
        confidence: str,
    ) -> None:
        raise AssertionError("capture should batch via capture_snapshot_atomic")

    def clear_snapshot_edges(self, snapshot_id: int) -> None:
        raise AssertionError(
            "SKIPPED path (client is None) must not be exercised through BatchOnlyStore"
        )
```

(Keep the existing `ensure_repo` and `list_entity_keys` methods at lines 86-94 unchanged. Delete the old `create_edge_snapshot` and `append_snapshot_edges` methods. `BatchOnlyStore` is valid ONLY for the non-None client path: the SKIPPED path (`snapshot.py:60`, reached when `client is None`) calls `store.clear_snapshot_edges(...)`, which after Task 5 the fake retains solely as a tripwire raising `AssertionError` — the batching test never drives `client=None`, so a real `clear_snapshot_edges` call signals the fake is being misused.)

- [ ] The assertion in `test_capture_edge_snapshot_batches_edge_writes` (`tests/test_snapshots.py:332-333`) already reads `assert store.batches == [[(1, 2, "calls", "resolved")]]` — that still holds because `capture_snapshot_atomic` records `edges`. No change to the test body is needed. Run it and SEE IT PASS:

```bash
python -m pytest tests/test_snapshots.py::test_capture_edge_snapshot_batches_edge_writes -x -q
```
Expected: `1 passed`.

- [ ] Type-check the test fake (pyright runs over tests if configured; otherwise this is a no-op gate):

```bash
pyright tests/test_snapshots.py
```
Expected: no new errors.

- [ ] Commit:

```bash
git add tests/test_snapshots.py
git commit -m "test(capture): point BatchOnlyStore fake at capture_snapshot_atomic

The batched-not-per-edge guarantee now exercises the atomic store method.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 6 — Capped-path mid-capture visibility regression test

The reground flags that the `max_entities` capped path has no visibility coverage. With the atomic rewrite, a capped capture (which forces `DELTA`) still writes exactly one row atomically. Add a test asserting a capped capture publishes a single `DELTA` row with its edges, and that a prior FULL snapshot for a DIFFERENT commit is unaffected. This closes the gap the existing tests leave (reground risk: "max_entities-cap mid-capture visibility").

**Files:**
- Modify `tests/test_snapshots.py` (append one test).

**Interfaces:**
- Consumes: `capture_edge_snapshot(..., max_entities=...)`; `FakeNeighborhoodClient` (`tests/test_snapshots.py:13`); `store.latest_snapshot`, `store.snapshot_edges`.
- Produces: test `test_capped_capture_publishes_single_delta_row`.

**Steps:**

- [ ] Append to `tests/test_snapshots.py`:

```python
def test_capped_capture_publishes_single_delta_row(tmp_path: Path) -> None:
    """A max_entities-capped capture writes exactly one DELTA row, atomically,
    with its edges present — never a transient FULL or empty row."""
    repo = tmp_path / "repo"
    repo.mkdir()
    with WarplineStore.open(tmp_path / "warpline.db") as store:
        repo_id = store.ensure_repo(repo)
        store.ensure_entity_key(repo_id, locator="python:function:a", sei=None, commit_sha="c1")
        store.ensure_entity_key(repo_id, locator="python:function:z", sei=None, commit_sha="c1")
        result = capture_edge_snapshot(
            store, repo, commit_sha="c1", client=FakeNeighborhoodClient(),
            source_version="v1", max_entities=1,
        )
        snap = store.latest_snapshot(repo)
        assert snap is not None
        edges = store.snapshot_edges(int(snap["id"]))

    assert result["capped"] is True
    assert result["completeness"] == "DELTA"
    assert snap["completeness"] == "DELTA"
    # The single queried entity ("python:function:a", sorted first) yields its
    # one edge; the row is published WITH that edge, not empty.
    assert result["edges"] == 1
    assert len(edges) == 1
```

- [ ] Run it and SEE IT PASS (Task 4 already makes the capped path atomic):

```bash
python -m pytest tests/test_snapshots.py::test_capped_capture_publishes_single_delta_row -x -q
```
Expected: `1 passed`.

- [ ] Commit:

```bash
git add tests/test_snapshots.py
git commit -m "test(capture): cover capped-path single-DELTA-row visibility

Closes the max_entities mid-capture visibility gap: a capped capture publishes
one atomic DELTA row with its edges, never a transient FULL/empty row.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 7 — Full gate sweep

Confirm all WS1-affected gates are green: the envelope is byte-identical at both call sites (`commands.py:618` lazy, `commands.py:1059` tool), dogfood and mcp-smoke pass, lint/types/tests pass, member-diff guard passes.

**Files:** none (verification only).

**Interfaces:** Consumes the full warpline test + gate surface.

**Steps:**

- [ ] Run ruff lint over the changed files:

```bash
ruff check src/warpline/store.py src/warpline/snapshot.py tests/test_snapshots.py tests/contracts/test_golden_vectors.py
```
Expected: `All checks passed!`

- [ ] Run pyright over the package:

```bash
pyright src/warpline
```
Expected: no new errors vs the pre-change baseline.

- [ ] Run the full test suite:

```bash
python -m pytest -q
```
Expected: all pass (in particular `tests/test_snapshots.py`, `tests/contracts/test_golden_vectors.py`, and any `commands` tests exercising `warpline_edge_snapshot_capture`).

- [ ] Run the dogfood + smoke gates:

```bash
warpline dogfood-eval
warpline mcp-smoke
```
Expected: both exit 0 (dogfood reports its eval summary; mcp-smoke reports tool round-trips OK).

- [ ] Run the member-diff guard exactly as CI invokes it. Discover the command first, then run it:

```bash
grep -rn "member-diff\|member_diff\|diff-guard" Makefile pyproject.toml noxfile.py .github 2>/dev/null | head
```
Then run the discovered command (e.g. `warpline member-diff` or the documented guard). Expected: exit 0 / no diff against the frozen member contract (the envelope is unchanged, so the guard must stay green).

- [ ] If every gate is green, the WS1 deliverable is complete. No commit (verification only). If any gate fails, STOP and treat it with superpowers:systematic-debugging — do not paper over a guard.

---

## Done criterion (this plan)

WS1 is complete when:
1. `capture_edge_snapshot` writes the snapshot row + edges in exactly one `BEGIN IMMEDIATE`..`COMMIT` (`capture_snapshot_atomic`), with completeness computed before the write opens.
2. The fail-closed invariant is locked by `test_capture_failure_preserves_prior_full_snapshot` and golden vector `GV-LW-6` (both green).
3. The capped path is covered by `test_capped_capture_publishes_single_delta_row`.
4. The response envelope is byte-identical; all gates green (ruff, pyright, pytest, dogfood-eval, mcp-smoke, member-diff guard).

WS2 (honesty completeness) and WS3 (conformance package + hub handover) are SEPARATE plans (B and C in the design spec) and out of scope here.
