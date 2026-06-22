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

from pathlib import Path

import pytest
from conftest import commit as _commit
from conftest import init_repo as _init_repo

from warpline import commands
from warpline.errors import InvalidChangedRefsError
from warpline.mcp import assert_inputschema_consumed
from warpline.store import WarplineStore, default_store_path


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


class _QuietCaptureClient:
    def __init__(self, repo: Path, command: str = "loomweave") -> None:
        self.calls: list[str] = []

    def neighborhood(self, entity: str) -> dict[str, object]:
        self.calls.append(entity)
        return {"entity": {"id": entity}, "truncated": {"callers": False, "callees": False}}

    def close(self) -> None:
        return None


def _make_loomweave_available(monkeypatch: pytest.MonkeyPatch) -> _QuietCaptureClient:
    client = _QuietCaptureClient(Path("."))
    monkeypatch.setattr(
        commands.LoomweaveProbe,
        "probe",
        lambda self: {"status": "available", "version": "test-loomweave"},
    )
    monkeypatch.setattr(commands, "LoomweaveMcpClient", lambda **kwargs: client)
    return client


@pytest.mark.parametrize(
    ("ref", "expected_query_entity"),
    [
        (
            {"kind": "path", "value": "src/pkg/app.py"},
            "python:function:pkg.app.target",
        ),
        (
            {"kind": "qualname", "value": "pkg.app.target"},
            "python:function:pkg.app.target",
        ),
        (
            {"kind": "sei", "value": "loomweave:eid:target"},
            "python:function:pkg.app.target",
        ),
    ],
)
def test_capture_changed_only_resolves_public_scope_refs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    ref: dict[str, str],
    expected_query_entity: str,
) -> None:
    repo = _init_repo(tmp_path)
    (repo / "src/pkg").mkdir(parents=True)
    head = _commit(repo, "src/pkg/app.py", "def target():\n    return 1\n")
    client = _make_loomweave_available(monkeypatch)
    with WarplineStore.open(default_store_path(repo)) as store:
        repo_id = store.ensure_repo(repo)
        store.ensure_entity_key(
            repo_id,
            locator="python:function:src/pkg/app.py::target",
            sei="loomweave:eid:target",
            commit_sha=head,
        )

    envelope = commands.capture_snapshot(
        repo,
        mode="changed_only",
        changed_refs=[ref],
    )

    assert envelope["data"]["completeness"] == "FULL"
    assert envelope["data"]["entities"] == 1
    assert client.calls == [expected_query_entity]


def test_capture_changed_only_unresolved_scope_is_delta_not_full(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _init_repo(tmp_path)
    (repo / "src/pkg").mkdir(parents=True)
    head = _commit(repo, "src/pkg/app.py", "def target():\n    return 1\n")
    client = _make_loomweave_available(monkeypatch)
    with WarplineStore.open(default_store_path(repo)) as store:
        repo_id = store.ensure_repo(repo)
        store.ensure_entity_key(
            repo_id,
            locator="python:function:src/pkg/app.py::target",
            sei="loomweave:eid:target",
            commit_sha=head,
        )

    envelope = commands.capture_snapshot(
        repo,
        mode="changed_only",
        changed_refs=[{"kind": "sei", "value": "loomweave:eid:missing"}],
    )

    assert envelope["data"]["completeness"] == "DELTA"
    assert envelope["data"]["entities"] == 0
    assert envelope["data"]["failed_entities"] == [
        {"locator": "sei:loomweave:eid:missing", "reason": "sei_not_in_snapshot"}
    ]
    assert envelope["enrichment"]["edges"] == "partial"
    assert client.calls == []


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


# --------------------------------------------------------------------------- (d)
def test_requirements_is_reserved_but_honest_on_every_tool(tmp_path: Path) -> None:
    """The reserved-but-inert ``requirements`` dimension must explain itself.

    ``requirements`` rides as scalar ``unavailable`` on every envelope but has no
    transport wired. Rather than a bare, unexplained scalar, it carries a stable
    ``disabled`` triple naming WHY (reserved, not yet wired) and the fix (the work
    that would wire it). The scalar value is unchanged — only the triple is added.
    """

    repo = _init_repo(tmp_path)
    _commit(repo, "a.py", "a = 1\n")
    env = commands.change_list(repo)

    assert env["enrichment"]["requirements"] == "unavailable"  # scalar untouched
    triple = env["enrichment_reasons"]["requirements"]
    assert triple["reason_class"] == "disabled"
    assert "reserved" in triple["cause"].lower()
    assert triple["fix"]


# --------------------------------------------------------------------------- (e)
def test_change_list_sei_absent_carries_unresolved_input_triple(tmp_path: Path) -> None:
    """A change_list over an entity with no SEI emits sei:absent WITH a triple
    explaining the locator never resolved — not a bare, unexplained scalar."""

    repo = _init_repo(tmp_path)
    first = _commit(repo, "a.py", "a = 1\n")
    with WarplineStore.open(default_store_path(repo)) as store:
        repo_id = store.ensure_repo(repo)
        key = store.ensure_entity_key(
            repo_id, locator="python:function:a", sei=None, commit_sha=first
        )
        store.append_change_event(
            repo_id=repo_id,
            entity_key_id=key,
            commit_sha=first,
            change_kind="modified",
            actor="agent:test",
            changed_at="2026-06-13T00:00:00Z",
            path="a.py",
        )
    env = commands.change_list(repo)
    assert env["enrichment"]["sei"] == "absent"
    assert env["enrichment_reasons"]["sei"]["reason_class"] == "unresolved_input"


def test_change_list_sei_present_is_clean_triple(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    first = _commit(repo, "a.py", "a = 1\n")
    with WarplineStore.open(default_store_path(repo)) as store:
        repo_id = store.ensure_repo(repo)
        key = store.ensure_entity_key(
            repo_id, locator="python:function:a", sei="loomweave:eid:aaaa", commit_sha=first
        )
        store.append_change_event(
            repo_id=repo_id,
            entity_key_id=key,
            commit_sha=first,
            change_kind="modified",
            actor="agent:test",
            changed_at="2026-06-13T00:00:00Z",
            path="a.py",
        )
    env = commands.change_list(repo)
    assert env["enrichment"]["sei"] == "present"
    assert env["enrichment_reasons"]["sei"] == {"reason_class": "clean"}


def test_entity_timeline_sei_absent_carries_unresolved_input_triple(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    first = _commit(repo, "a.py", "a = 1\n")
    with WarplineStore.open(default_store_path(repo)) as store:
        repo_id = store.ensure_repo(repo)
        key = store.ensure_entity_key(
            repo_id, locator="python:function:a", sei=None, commit_sha=first
        )
        store.append_change_event(
            repo_id=repo_id,
            entity_key_id=key,
            commit_sha=first,
            change_kind="modified",
            actor="agent:test",
            changed_at="2026-06-13T00:00:00Z",
            path="a.py",
        )
    env = commands.entity_timeline(repo, "python:function:a")
    assert env["enrichment"]["sei"] == "absent"
    assert env["enrichment_reasons"]["sei"]["reason_class"] == "unresolved_input"


def test_entity_churn_count_sei_absent_carries_unresolved_input_triple(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    _commit(repo, "a.py", "a = 1\n")
    env = commands.entity_churn_count(repo, [{"kind": "locator", "value": "python:function:a"}])
    assert env["enrichment"]["sei"] == "absent"
    assert env["enrichment_reasons"]["sei"]["reason_class"] == "unresolved_input"


# --------------------------------------------------------------------------- (f)
def test_capture_sei_unavailable_carries_unreachable_triple(tmp_path: Path) -> None:
    """Capture against an unreachable Loomweave emits sei:unavailable WITH an
    unreachable triple (peer down) — never an implied clean/resolved state."""

    repo = _init_repo(tmp_path)
    _commit(repo, "a.py", "a = 1\n")
    env = commands.capture_snapshot(repo, commit="HEAD", loomweave_command="/no/such")
    assert env["enrichment"]["sei"] == "unavailable"
    assert env["enrichment_reasons"]["sei"]["reason_class"] == "unreachable"
    assert "loomweave" in env["enrichment_reasons"]["sei"]["cause"].lower()


def test_entity_timeline_governance_unavailable_carries_disabled_triple(tmp_path: Path) -> None:
    """Without a rename-feed transport, governance is unavailable WITH a disabled
    triple (no transport wired) — not a bare scalar."""

    repo = _init_repo(tmp_path)
    first = _commit(repo, "a.py", "a = 1\n")
    with WarplineStore.open(default_store_path(repo)) as store:
        repo_id = store.ensure_repo(repo)
        key = store.ensure_entity_key(
            repo_id, locator="python:function:a", sei=None, commit_sha=first
        )
        store.append_change_event(
            repo_id=repo_id,
            entity_key_id=key,
            commit_sha=first,
            change_kind="modified",
            actor="agent:test",
            changed_at="2026-06-13T00:00:00Z",
            path="a.py",
        )
    env = commands.entity_timeline(repo, "python:function:a")
    assert env["enrichment"]["governance"] == "unavailable"
    assert env["enrichment_reasons"]["governance"]["reason_class"] == "disabled"
    assert env["enrichment_reasons"]["governance"]["fix"]


def test_entity_timeline_governance_present_is_clean_triple(tmp_path: Path) -> None:
    from warpline.siblings import RenameFeed

    repo = _init_repo(tmp_path)
    first = _commit(repo, "a.py", "a = 1\n")
    with WarplineStore.open(default_store_path(repo)) as store:
        repo_id = store.ensure_repo(repo)
        key = store.ensure_entity_key(
            repo_id, locator="python:function:a", sei=None, commit_sha=first
        )
        store.append_change_event(
            repo_id=repo_id,
            entity_key_id=key,
            commit_sha=first,
            change_kind="modified",
            actor="agent:test",
            changed_at="2026-06-13T00:00:00Z",
            path="a.py",
        )
    feed = RenameFeed([{"old_locator": "python:function:a", "new_locator": "python:function:a"}])
    env = commands.entity_timeline(repo, "python:function:a", rename_feed=feed)
    assert env["enrichment"]["governance"] == "present"
    assert env["enrichment_reasons"]["governance"] == {"reason_class": "clean"}
