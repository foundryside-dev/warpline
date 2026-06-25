from __future__ import annotations

from pathlib import Path

from conftest import commit as _commit
from conftest import init_repo as _init_repo

from warpline.propagation import blast_radius
from warpline.snapshot import capture_edge_snapshot, record_skipped_snapshot
from warpline.store import WarplineStore


class FakeNeighborhoodClient:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def neighborhood(self, entity: str) -> dict[str, object]:
        self.calls.append(entity)
        if entity == "python:function:a":
            return {
                "entity": {"id": "python:function:a"},
                "callees": [{"id": "python:function:b"}],
                "truncated": {"callers": False, "callees": False},
            }
        return {
            "entity": {"id": entity},
            "truncated": {"callers": False, "callees": False},
        }


class MidCaptureReaderClient:
    def __init__(self, db_path: Path, repo: Path) -> None:
        self.db_path = db_path
        self.repo = repo
        self.observed_latest: dict[str, object] | None = None
        self.observed_edges: list[dict[str, object]] = []

    def neighborhood(self, entity: str) -> dict[str, object]:
        with WarplineStore.open(self.db_path) as reader:
            self.observed_latest = reader.latest_snapshot(self.repo)
            if self.observed_latest is not None:
                self.observed_edges = reader.snapshot_edges(int(self.observed_latest["id"]))
        if entity == "python:function:a":
            return {
                "entity": {"id": "python:function:a"},
                "callees": [{"id": "python:function:b"}],
                "truncated": {"callers": False, "callees": False},
            }
        return {
            "entity": {"id": entity},
            "truncated": {"callers": False, "callees": False},
        }


class TruncatedNeighborhoodClient:
    def neighborhood(self, entity: str) -> dict[str, object]:
        return {
            "entity": {"id": entity},
            "callees": [{"id": "python:function:b"}],
            "truncated": {"callers": False, "callees": True},
        }


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


class LoomweaveIdNeighborhoodClient:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def neighborhood(self, entity: str) -> dict[str, object]:
        self.calls.append(entity)
        if entity != "python:function:pkg.mod.changed":
            return {
                "entity": {"id": entity},
                "truncated": {"callers": False, "callees": False},
            }
        return {
            "entity": {"id": "python:function:pkg.mod.changed"},
            "callees": [{"id": "python:function:pkg.other.affected"}],
            "truncated": {"callers": False, "callees": False},
        }


class BatchOnlyStore:
    def __init__(self) -> None:
        self.batches: list[list[tuple[int, int, str, str]]] = []

    def ensure_repo(self, repo: Path) -> str:
        return "repo-id"

    def list_entity_keys(self, repo: Path) -> list[dict[str, object]]:
        return [
            {"id": 1, "locator": "python:function:a", "sei": None},
            {"id": 2, "locator": "python:function:b", "sei": None},
            {"id": 3, "locator": "python:function:c", "sei": None},
        ]

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


def test_skipped_snapshot_is_queryable(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    with WarplineStore.open(tmp_path / "warpline.db") as store:
        repo_id = store.ensure_repo(repo)
        record_skipped_snapshot(store, repo_id, "abc123", reason="no_index")
        snap = store.latest_snapshot(repo)

    assert snap is not None
    assert snap["completeness"] == "SKIPPED"
    assert snap["source"] == "loomweave"
    assert snap["source_version"] == "no_index"


def test_capture_edge_snapshot_records_loomweave_edges(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    client = FakeNeighborhoodClient()
    with WarplineStore.open(tmp_path / "warpline.db") as store:
        repo_id = store.ensure_repo(repo)
        a = store.ensure_entity_key(
            repo_id, locator="python:function:a", sei=None, commit_sha="c1"
        )
        result = capture_edge_snapshot(
            store,
            repo,
            commit_sha="c1",
            client=client,
            source_version="test-client",
        )
        snapshot = store.latest_snapshot(repo)
        assert snapshot is not None
        edges = store.snapshot_edges(int(snapshot["id"]))

    assert result["completeness"] == "FULL"
    assert result["edges"] == 1
    assert client.calls == ["python:function:a"]
    assert edges == [
        {
            "source_entity_key_id": a,
            "target_entity_key_id": a + 1,
            "edge_kind": "calls",
            "confidence": "resolved",
        }
    ]


def test_capture_edge_snapshot_resolves_symbolic_commit_before_storing(
    tmp_path: Path,
) -> None:
    repo = _init_repo(tmp_path)
    first = _commit(repo, "a.py", "a = 1\n")
    client = FakeNeighborhoodClient()
    with WarplineStore.open(tmp_path / "warpline.db") as store:
        repo_id = store.ensure_repo(repo)
        a = store.ensure_entity_key(
            repo_id, locator="python:function:a", sei=None, commit_sha=first
        )
        result = capture_edge_snapshot(
            store,
            repo,
            commit_sha="HEAD",
            client=client,
            source_version="test-client",
        )
        snapshot = store.latest_snapshot(repo)

    assert result["commit_sha"] == first
    assert snapshot is not None
    assert snapshot["commit_sha"] == first

    _commit(repo, "a.py", "a = 2\n")

    with WarplineStore.open(tmp_path / "warpline.db") as store:
        stale = blast_radius(store, repo, [a], depth=2)

    assert stale["staleness"]["snapshot_commit"] == first
    assert stale["staleness"]["commits_behind"] == 1


def test_capture_edge_snapshot_does_not_publish_full_until_edges_complete(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    db_path = tmp_path / "warpline.db"
    client = MidCaptureReaderClient(db_path, repo)
    with WarplineStore.open(db_path) as store:
        repo_id = store.ensure_repo(repo)
        store.ensure_entity_key(repo_id, locator="python:function:a", sei=None, commit_sha="c1")
        result = capture_edge_snapshot(
            store,
            repo,
            commit_sha="c1",
            client=client,
            source_version="test-client",
        )
        final_snapshot = store.latest_snapshot(repo)
        assert final_snapshot is not None
        final_edges = store.snapshot_edges(int(final_snapshot["id"]))

    assert client.observed_edges == []
    assert (
        client.observed_latest is None
        or client.observed_latest["completeness"] != "FULL"
    )
    assert result["completeness"] == "FULL"
    assert final_snapshot["completeness"] == "FULL"
    assert len(final_edges) == 1


def test_capture_edge_snapshot_maps_loomweave_ids_back_to_warpline_keys(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    client = LoomweaveIdNeighborhoodClient()
    with WarplineStore.open(tmp_path / "warpline.db") as store:
        repo_id = store.ensure_repo(repo)
        changed = store.ensure_entity_key(
            repo_id, locator="python:function:pkg/mod.py::changed", sei=None, commit_sha="c1"
        )
        affected = store.ensure_entity_key(
            repo_id, locator="python:function:pkg/other.py::affected", sei=None, commit_sha="c1"
        )
        result = capture_edge_snapshot(
            store,
            repo,
            commit_sha="c1",
            client=client,
            source_version="test-client",
        )
        snapshot = store.latest_snapshot(repo)
        assert snapshot is not None
        edges = store.snapshot_edges(int(snapshot["id"]))

    assert result["completeness"] == "FULL"
    assert client.calls == [
        "python:function:pkg.mod.changed",
        "python:function:pkg.other.affected",
    ]
    assert {
        "source_entity_key_id": changed,
        "target_entity_key_id": affected,
        "edge_kind": "calls",
        "confidence": "resolved",
    } in edges


def test_capture_skipped_preserves_prior_full_snapshot(tmp_path: Path) -> None:
    """Loomweave absent at re-capture must NOT downgrade a usable prior FULL
    snapshot to a 0-edge SKIPPED row (R3 data-loss). The prior graph is real;
    overwriting it with "we don't know" is strictly worse. Preserve it intact
    and report the recapture as skipped (fail-closed / enrich-only doctrine)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    with WarplineStore.open(tmp_path / "warpline.db") as store:
        repo_id = store.ensure_repo(repo)
        a = store.ensure_entity_key(
            repo_id, locator="python:function:a", sei=None, commit_sha="c1"
        )
        b = store.ensure_entity_key(
            repo_id, locator="python:function:b", sei=None, commit_sha="c1"
        )
        prior_id = store.create_edge_snapshot(repo_id, "c1", "loomweave", "old", "FULL")
        store.append_snapshot_edge(
            prior_id,
            source_entity_key_id=a,
            target_entity_key_id=b,
            edge_kind="calls",
            confidence="resolved",
        )

        result = capture_edge_snapshot(
            store,
            repo,
            commit_sha="c1",
            client=None,
            source_version="no_index",
        )
        edges = store.snapshot_edges(prior_id)
        snapshot = store.latest_snapshot(repo)

    # The prior FULL snapshot and its edge survive untouched.
    assert len(edges) == 1
    assert snapshot is not None
    assert int(snapshot["id"]) == prior_id
    assert snapshot["completeness"] == "FULL"
    assert snapshot["source_version"] == "old"
    # The capture result honestly reports the preserved row, not a fresh SKIPPED.
    assert result["snapshot_id"] == prior_id
    assert result["completeness"] == "FULL"
    assert result["recapture_skipped"] is True
    assert result["entities"] == 0
    assert result["edges"] == 0


def test_capture_skipped_preserves_prior_delta_snapshot(tmp_path: Path) -> None:
    """A partial-but-real DELTA prior is also preserved (not downgraded to
    SKIPPED) when loomweave is absent at re-capture — its edges are still real."""
    repo = tmp_path / "repo"
    repo.mkdir()
    with WarplineStore.open(tmp_path / "warpline.db") as store:
        repo_id = store.ensure_repo(repo)
        a = store.ensure_entity_key(
            repo_id, locator="python:function:a", sei=None, commit_sha="c1"
        )
        b = store.ensure_entity_key(
            repo_id, locator="python:function:b", sei=None, commit_sha="c1"
        )
        prior_id = store.create_edge_snapshot(repo_id, "c1", "loomweave", "old", "DELTA")
        store.append_snapshot_edge(
            prior_id,
            source_entity_key_id=a,
            target_entity_key_id=b,
            edge_kind="calls",
            confidence="resolved",
        )

        result = capture_edge_snapshot(
            store, repo, commit_sha="c1", client=None, source_version="no_index"
        )
        edges = store.snapshot_edges(prior_id)
        snapshot = store.latest_snapshot(repo)

    assert len(edges) == 1
    assert snapshot is not None
    assert snapshot["completeness"] == "DELTA"
    assert snapshot["source_version"] == "old"
    assert result["completeness"] == "DELTA"
    assert result["recapture_skipped"] is True


def test_capture_skipped_without_prior_writes_skipped_atomically(tmp_path: Path) -> None:
    """With no usable prior, a loomweave-absent capture records a single SKIPPED
    row (no edges), written in one transaction — not the old two-commit
    (UPSERT then DELETE) dance. There is nothing to corrupt, so SKIPPED is the
    honest 'we have nothing' marker here."""
    repo = tmp_path / "repo"
    repo.mkdir()
    with WarplineStore.open(tmp_path / "warpline.db") as store:
        repo_id = store.ensure_repo(repo)
        result = capture_edge_snapshot(
            store, repo, commit_sha="c1", client=None, source_version="no_index"
        )
        snapshot = store.latest_snapshot(repo)
        assert snapshot is not None
        edges = store.snapshot_edges(int(snapshot["id"]))

    assert snapshot["completeness"] == "SKIPPED"
    assert snapshot["source_version"] == "no_index"
    assert edges == []
    assert result["completeness"] == "SKIPPED"
    assert result["snapshot_id"] == int(snapshot["id"])
    assert "recapture_skipped" not in result


def test_capture_edge_snapshot_batches_edge_writes(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    store = BatchOnlyStore()
    result = capture_edge_snapshot(
        store,  # type: ignore[arg-type]
        repo,
        commit_sha="c1",
        client=FakeNeighborhoodClient(),
        source_version="test-client",
    )

    assert result["edges"] == 1
    assert store.batches == [[(1, 2, "calls", "resolved")]]


def test_capture_edge_snapshot_degrades_truncated_neighborhood_to_delta(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    with WarplineStore.open(tmp_path / "warpline.db") as store:
        repo_id = store.ensure_repo(repo)
        store.ensure_entity_key(repo_id, locator="python:function:a", sei=None, commit_sha="c1")
        result = capture_edge_snapshot(
            store,
            repo,
            commit_sha="c1",
            client=TruncatedNeighborhoodClient(),
            source_version="test-client",
        )
        snapshot = store.latest_snapshot(repo)
        assert snapshot is not None
        edges = store.snapshot_edges(int(snapshot["id"]))

    assert result["completeness"] == "DELTA"
    assert result["failed_entities"] == [
        {
            "locator": "python:function:a",
            "reason": "truncated neighborhood cannot be snapshotted as complete",
        }
    ]
    assert snapshot["completeness"] == "DELTA"
    assert edges == []


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


def test_capped_capture_publishes_single_delta_row(tmp_path: Path) -> None:
    """A max_entities-capped capture writes exactly one DELTA row, atomically,
    with its edges present — never a transient FULL or empty row."""
    repo = tmp_path / "repo"
    repo.mkdir()
    with WarplineStore.open(tmp_path / "warpline.db") as store:
        repo_id = store.ensure_repo(repo)
        store.ensure_entity_key(
            repo_id, locator="python:function:a", sei=None, commit_sha="c1"
        )
        store.ensure_entity_key(
            repo_id, locator="python:function:z", sei=None, commit_sha="c1"
        )
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
