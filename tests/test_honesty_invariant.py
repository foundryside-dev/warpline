"""PDR-0023 honesty-invariant tests for warpline change-impact.

These pin the three coupled fixes that make warpline's quiet, fail-open posture
LOUD: (a) a stale snapshot downgrades completeness and emits the live
``edges:"stale"`` vocab instead of a confident ``edges:"present"``; (b) an
unresolved changed-ref returns a machine-readable miss-set instead of being
silently dropped from the affected-set seed; (c) every advertised capture
inputSchema field is honored or rejected — never advertised-and-ignored — and a
startup assertion proves it.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from warpline import commands
from warpline.errors import InvalidChangedRefsError
from warpline.mcp import assert_inputschema_consumed
from warpline.store import WarplineStore, default_store_path


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, text=True, stdout=subprocess.PIPE
    ).stdout.strip()


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "agent@example.test")
    _git(repo, "config", "user.name", "Agent")
    return repo


def _commit(repo: Path, name: str, body: str) -> str:
    (repo / name).write_text(body, encoding="utf-8")
    _git(repo, "add", name)
    _git(repo, "commit", "-m", f"write {name}")
    return _git(repo, "rev-parse", "HEAD")


# --------------------------------------------------------------------------- (a)
def test_stale_but_full_snapshot_emits_edges_stale_GOLDEN_VECTOR(tmp_path: Path) -> None:
    """GOLDEN VECTOR — the stale-but-FULL-snapshot path.

    A snapshot captured at an earlier commit, with a genuine downstream edge
    (a -> b) and completeness FULL, must NOT hand the agent a confident
    affected-set with ``edges:"present"`` once HEAD has moved past it. It must
    surface freshness honestly: ``enrichment.edges == "stale"`` plus a STALE
    warning naming the commits-behind count. This is the difference between
    "your change breaks b (trust me)" and "your change breaks b, but my graph is
    1 commit behind HEAD — recapture before trusting completeness".
    """

    repo = _init_repo(tmp_path)
    first = _commit(repo, "a.py", "a = 1\n")

    with WarplineStore.open(default_store_path(repo)) as store:
        repo_id = store.ensure_repo(repo)
        a = store.ensure_entity_key(
            repo_id, locator="python:function:a", sei=None, commit_sha=first
        )
        b = store.ensure_entity_key(
            repo_id, locator="python:function:b", sei=None, commit_sha=first
        )
        snap = store.create_edge_snapshot(repo_id, first, "loomweave", "test", "FULL")
        store.append_snapshot_edge(
            snap,
            source_entity_key_id=a,
            target_entity_key_id=b,
            edge_kind="calls",
            confidence="resolved",
        )

    # Move HEAD past the snapshot commit — the FULL snapshot is now stale.
    _commit(repo, "a.py", "a = 2\n")

    envelope = commands.impact_radius(repo, [a], depth=2)

    # The edge is real and the snapshot is FULL: the affected-set is non-empty.
    assert envelope["data"]["completeness"] == "FULL"
    assert [row["entity"]["locator"] for row in envelope["data"]["affected"]] == [
        "python:function:b"
    ]
    # ...but freshness is surfaced honestly, not silently presented as complete.
    assert envelope["enrichment"]["edges"] == "stale"
    assert envelope["data"]["staleness"]["commits_behind"] == 1
    assert any(w.startswith("STALE:") for w in envelope["warnings"])


def test_fresh_full_snapshot_still_emits_edges_present(tmp_path: Path) -> None:
    """The downgrade is strictly staleness-gated: a snapshot AT HEAD stays
    ``edges:"present"`` with no STALE warning (no false alarms)."""

    repo = _init_repo(tmp_path)
    head = _commit(repo, "a.py", "a = 1\n")

    with WarplineStore.open(default_store_path(repo)) as store:
        repo_id = store.ensure_repo(repo)
        a = store.ensure_entity_key(
            repo_id, locator="python:function:a", sei=None, commit_sha=head
        )
        b = store.ensure_entity_key(
            repo_id, locator="python:function:b", sei=None, commit_sha=head
        )
        snap = store.create_edge_snapshot(repo_id, head, "loomweave", "test", "FULL")
        store.append_snapshot_edge(
            snap,
            source_entity_key_id=a,
            target_entity_key_id=b,
            edge_kind="calls",
            confidence="resolved",
        )

    envelope = commands.impact_radius(repo, [a], depth=2)
    assert envelope["enrichment"]["edges"] == "present"
    assert envelope["data"]["staleness"]["commits_behind"] == 0
    assert not any(w.startswith("STALE:") for w in envelope["warnings"])


def test_reverify_worklist_also_downgrades_on_stale(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    first = _commit(repo, "a.py", "a = 1\n")
    with WarplineStore.open(default_store_path(repo)) as store:
        repo_id = store.ensure_repo(repo)
        a = store.ensure_entity_key(
            repo_id, locator="python:function:a", sei=None, commit_sha=first
        )
        store.create_edge_snapshot(repo_id, first, "loomweave", "test", "FULL")
    _commit(repo, "a.py", "a = 2\n")
    envelope = commands.reverify_worklist(repo, [a], depth=2)
    assert envelope["enrichment"]["edges"] == "stale"
    assert any(w.startswith("STALE:") for w in envelope["warnings"])


# --------------------------------------------------------------------------- (b)
def test_unresolved_ref_returns_miss_set_not_silent_drop(tmp_path: Path) -> None:
    """An SEI that does not resolve into the store appears in ``data.unresolved``
    with a reason, alongside ``data.resolved`` for the ones that did — so an
    agent can ask 'did my SEI resolve into the snapshot?' and get a yes/no."""

    repo = _init_repo(tmp_path)
    head = _commit(repo, "a.py", "a = 1\n")
    with WarplineStore.open(default_store_path(repo)) as store:
        repo_id = store.ensure_repo(repo)
        store.ensure_entity_key(
            repo_id,
            locator="python:function:a",
            sei="loomweave:eid:known",
            commit_sha=head,
        )
        store.create_edge_snapshot(repo_id, head, "loomweave", "test", "FULL")

    envelope = commands.impact_radius(
        repo,
        changed_refs=[
            {"kind": "sei", "value": "loomweave:eid:known"},
            {"kind": "sei", "value": "loomweave:eid:ghost"},
        ],
        depth=2,
    )
    resolved = {r["ref"]["value"] for r in envelope["data"]["resolved"]}
    unresolved = {u["ref"]["value"]: u["reason"] for u in envelope["data"]["unresolved"]}
    assert resolved == {"loomweave:eid:known"}
    assert unresolved == {"loomweave:eid:ghost": "sei_not_in_snapshot"}
    assert any(w.startswith("UNRESOLVED:") for w in envelope["warnings"])


def test_all_refs_resolve_means_empty_miss_set(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    head = _commit(repo, "a.py", "a = 1\n")
    with WarplineStore.open(default_store_path(repo)) as store:
        repo_id = store.ensure_repo(repo)
        store.ensure_entity_key(
            repo_id, locator="python:function:a", sei="loomweave:eid:k", commit_sha=head
        )
        store.create_edge_snapshot(repo_id, head, "loomweave", "test", "FULL")
    envelope = commands.impact_radius(
        repo, changed_refs=[{"kind": "sei", "value": "loomweave:eid:k"}], depth=2
    )
    assert envelope["data"]["unresolved"] == []
    assert len(envelope["data"]["resolved"]) == 1
    assert not any(w.startswith("UNRESOLVED:") for w in envelope["warnings"])


def test_unknown_entity_key_id_is_a_miss(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    head = _commit(repo, "a.py", "a = 1\n")
    with WarplineStore.open(default_store_path(repo)) as store:
        repo_id = store.ensure_repo(repo)
        store.create_edge_snapshot(repo_id, head, "loomweave", "test", "FULL")
    envelope = commands.impact_radius(repo, [424242], depth=2)
    assert envelope["data"]["unresolved"] == [
        {
            "ref": {"kind": "warpline_entity_key_id", "value": 424242},
            "reason": "unknown_entity_key_id",
        }
    ]


# --------------------------------------------------------------------------- (c)
def test_startup_assertion_passes_for_live_schema() -> None:
    # Imported at module load; calling it again must stay green (no raise).
    assert_inputschema_consumed()


def test_startup_assertion_catches_a_newly_dead_field(monkeypatch: pytest.MonkeyPatch) -> None:
    """If a future edit advertises a capture field nothing consumes, the
    assertion must FAIL — proving it is a live guard, not a no-op."""

    from warpline import mcp

    poisoned = []
    for spec in mcp.TOOL_SPECS:
        spec = dict(spec)
        if spec["endorsed"] == "warpline_edge_snapshot_capture":
            schema = {**spec["inputSchema"]}
            schema["properties"] = {**schema["properties"], "phantom_knob": {"type": "string"}}
            spec["inputSchema"] = schema
        poisoned.append(spec)
    monkeypatch.setattr(mcp, "TOOL_SPECS", poisoned)
    with pytest.raises(AssertionError, match="phantom_knob"):
        mcp.assert_inputschema_consumed()


def test_capture_rejects_bad_max_entities(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    _commit(repo, "a.py", "a = 1\n")
    with pytest.raises(InvalidChangedRefsError):
        commands.capture_snapshot(repo, max_entities=0)
    with pytest.raises(InvalidChangedRefsError):
        commands.capture_snapshot(repo, max_entities="lots")


def test_capture_rejects_bad_if_stale_after(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    _commit(repo, "a.py", "a = 1\n")
    with pytest.raises(InvalidChangedRefsError):
        commands.capture_snapshot(repo, if_stale_after=12345)


def test_capture_changed_only_requires_refs(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    _commit(repo, "a.py", "a = 1\n")
    with pytest.raises(InvalidChangedRefsError):
        commands.capture_snapshot(repo, mode="changed_only")


def test_capture_echoes_idempotency_key(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    _commit(repo, "a.py", "a = 1\n")
    # No loomweave in the test env -> SKIPPED, but the key must round-trip.
    envelope = commands.capture_snapshot(repo, idempotency_key="req-7")
    assert envelope["data"]["idempotency_key"] == "req-7"


def test_max_entities_cap_downgrades_to_delta(tmp_path: Path) -> None:
    """A capture capped below the known entity count is a partial graph and must
    report DELTA + capped, never FULL — a confident affected-set over a
    deliberately-truncated graph is the fail-open posture this strike kills."""

    from warpline.snapshot import capture_edge_snapshot

    repo = tmp_path / "repo"
    repo.mkdir()

    class Quiet:
        def neighborhood(self, entity: str) -> dict[str, object]:
            return {"entity": {"id": entity}, "truncated": {"callers": False, "callees": False}}

    with WarplineStore.open(default_store_path(repo)) as store:
        repo_id = store.ensure_repo(repo)
        for i in range(3):
            store.ensure_entity_key(
                repo_id, locator=f"python:function:e{i}", sei=None, commit_sha="c1"
            )
        result = capture_edge_snapshot(
            store, repo, commit_sha="c1", client=Quiet(), source_version="t", max_entities=2
        )
    assert result["capped"] is True
    assert result["completeness"] == "DELTA"
    assert result["entities"] == 2


def test_changed_only_scope_limits_captured_entities(tmp_path: Path) -> None:
    from warpline.snapshot import capture_edge_snapshot

    repo = tmp_path / "repo"
    repo.mkdir()
    seen: list[str] = []

    class Recorder:
        def neighborhood(self, entity: str) -> dict[str, object]:
            seen.append(entity)
            return {"entity": {"id": entity}, "truncated": {"callers": False, "callees": False}}

    with WarplineStore.open(default_store_path(repo)) as store:
        repo_id = store.ensure_repo(repo)
        for loc in ("python:function:keep", "python:function:drop"):
            store.ensure_entity_key(repo_id, locator=loc, sei=None, commit_sha="c1")
        capture_edge_snapshot(
            store,
            repo,
            commit_sha="c1",
            client=Recorder(),
            source_version="t",
            scope_locators={"python:function:keep"},
        )
    assert "python:function:keep" in seen
    assert "python:function:drop" not in seen


def test_capture_if_stale_after_short_circuits(tmp_path: Path) -> None:
    """A current snapshot captured at-or-after the watermark skips recapture and
    reports already_current with a FRESH warning — the field is honored, not
    ignored."""

    repo = _init_repo(tmp_path)
    head = _commit(repo, "a.py", "a = 1\n")
    with WarplineStore.open(default_store_path(repo)) as store:
        repo_id = store.ensure_repo(repo)
        store.create_edge_snapshot(repo_id, head, "loomweave", "test", "FULL")
        captured_at = str(store.latest_snapshot(repo)["captured_at"])

    envelope = commands.capture_snapshot(repo, if_stale_after=captured_at)
    assert envelope["data"]["idempotency"] == "already_current"
    assert any(w.startswith("FRESH:") for w in envelope["warnings"])
