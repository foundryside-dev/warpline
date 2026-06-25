"""The 19 FROZEN golden vectors (interface-lock §1D, 2C, 3C, 4C).

These are warpline's contribution as the 5th producer to the four-member
conformance oracle (GS-7). Each test is one frozen (input → output assertion)
vector; the GV id in the name maps 1:1 to the spec table.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from warpline import commands
from warpline.siblings import RenameFeed, work_enrichment_for_sei
from warpline.snapshot import capture_edge_snapshot
from warpline.store import WarplineStore, default_store_path

ALL_TOOLS = "GV-LG-3"


# --------------------------------------------------------------------------- helpers
def _git(repo: Path, args: list[str]) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, text=True, capture_output=True
    ).stdout


def _git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, ["init"])
    _git(repo, ["config", "user.email", "agent@example.test"])
    _git(repo, ["config", "user.name", "agent:codex"])
    (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
    _git(repo, ["add", "."])
    _git(repo, ["commit", "-m", "seed"])
    return repo


def _store(repo: Path) -> WarplineStore:
    return WarplineStore.open(default_store_path(repo))


def _seed_entity(
    store: WarplineStore, repo_id: str, locator: str, sei: str | None, commit: str = "c1"
) -> int:
    return store.ensure_entity_key(repo_id, locator=locator, sei=sei, commit_sha=commit)


def _add_change(
    store: WarplineStore,
    repo_id: str,
    key_id: int,
    *,
    path: str,
    commit: str = "c1",
    kind: str = "modified",
    actor: str = "agent:codex",
    changed_at: str = "2026-06-13T00:00:00Z",
) -> None:
    store.append_change_event(
        repo_id=repo_id,
        entity_key_id=key_id,
        commit_sha=commit,
        path=path,
        change_kind=kind,
        actor=actor,
        changed_at=changed_at,
    )


def _commit_file(repo: Path, name: str, body: str) -> str:
    """Write *name* to *repo*, git-add, commit, and return the resolved HEAD SHA."""
    (repo / name).write_text(body)
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", f"touch {name}"],
        cwd=repo, check=True, capture_output=True,
    )
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo, check=True, text=True, capture_output=True,
    ).stdout.strip()


class _FullNeighborhoodClient:
    def neighborhood(self, entity: str) -> dict[str, Any]:
        if entity == "python:function:pkg.mod.a":
            return {
                "entity": {"id": "python:function:pkg.mod.a"},
                "callees": [{"id": "python:function:pkg.mod.b"}],
                "truncated": {"callers": False, "callees": False},
            }
        return {"entity": {"id": entity}, "truncated": {"callers": False, "callees": False}}


class _TruncatedNeighborhoodClient:
    def neighborhood(self, entity: str) -> dict[str, Any]:
        return {
            "entity": {"id": entity},
            "callees": [{"id": "python:function:pkg.mod.b"}],
            "truncated": {"callers": True, "callees": False},
        }


class _ExplodingNeighborhoodClient:
    """Hard mid-capture kill (BaseException, not Exception) for GV-LW-6."""

    def neighborhood(self, entity: str) -> dict[str, Any]:
        raise KeyboardInterrupt("loomweave killed mid-capture")


class _FixtureWorkClient:
    """A controlled filigree implementing the ADR-029 reverse-lookup + issue_get
    seam with real-shaped payloads."""

    def __init__(self, bound: dict[str, dict[str, Any]]) -> None:
        self._bound = bound

    def associations(self, sei: str) -> list[dict[str, Any]]:
        issue = self._bound.get(sei)
        if issue is None:
            return []
        return [{"issue_id": issue["id"], "entity_kind": "function"}]

    def issue(self, issue_id: str) -> dict[str, Any]:
        for issue in self._bound.values():
            if issue["id"] == issue_id:
                return issue
        return {}


# ============================================================ SEAM 1 — loomweave
def test_gv_lw_1_change_list_carries_locator_sei_and_next_action(tmp_path: Path) -> None:
    repo = _git_repo(tmp_path)
    with _store(repo) as store:
        repo_id = store.ensure_repo(repo)
        a = _seed_entity(store, repo_id, "python:function:m.py::a", "loomweave:eid:aaaa", "h")
        b = _seed_entity(store, repo_id, "python:function:m.py::b", "loomweave:eid:bbbb", "h")
        _add_change(store, repo_id, a, path="m.py", commit="h")
        _add_change(store, repo_id, b, path="m.py", commit="h")

    env = commands.change_list(repo)
    items = env["data"]["items"]
    assert len(items) == 2
    for item in items:
        assert "locator" in item["entity"] and "sei" in item["entity"]
        assert item["entity"]["sei"].startswith("loomweave:eid:")
    assert all(ref["kind"] == "sei" for ref in env["data"]["changed_refs"])
    assert "warpline_reverify_worklist_get" in env["next_actions"]
    assert env["enrichment"]["sei"] == "present"


def test_gv_lw_2_churn_count_includes_unobserved_as_zero(tmp_path: Path) -> None:
    repo = _git_repo(tmp_path)
    with _store(repo) as store:
        repo_id = store.ensure_repo(repo)
        a = _seed_entity(store, repo_id, "python:function:m.py::a", "loomweave:eid:aaaa")
        b = _seed_entity(store, repo_id, "python:function:m.py::b", "loomweave:eid:bbbb")
        _add_change(store, repo_id, a, path="m.py", commit="c1")
        _add_change(store, repo_id, a, path="m.py", commit="c2")
        _add_change(store, repo_id, b, path="m.py", commit="c1")

    env = commands.entity_churn_count(
        repo,
        [
            {"kind": "sei", "value": "loomweave:eid:aaaa"},
            {"kind": "sei", "value": "loomweave:eid:bbbb"},
            {"kind": "sei", "value": "loomweave:eid:never-observed"},
        ],
    )
    items = {i["entity"]["sei"]: i for i in env["data"]["items"]}
    assert len(items) == 3
    assert items["loomweave:eid:aaaa"]["churn_count"] >= 1
    assert items["loomweave:eid:bbbb"]["churn_count"] >= 1
    unobserved = items["loomweave:eid:never-observed"]
    assert unobserved["churn_count"] == 0  # not omitted, not an error


def test_gv_lw_3_capture_full_then_skipped(tmp_path: Path) -> None:
    repo = _git_repo(tmp_path)
    with _store(repo) as store:
        repo_id = store.ensure_repo(repo)
        _seed_entity(store, repo_id, "python:function:pkg/mod.py::a", None)
        _seed_entity(store, repo_id, "python:function:pkg/other.py::b", None)
        full = capture_edge_snapshot(
            store, repo, commit_sha="c1", client=_FullNeighborhoodClient(), source_version="t"
        )
    assert full["completeness"] == "FULL"
    assert full["edges"] > 0

    # The frozen contract is "loomweave absent -> SKIPPED" for a commit with no
    # usable prior. Exercise it at a DISTINCT commit (c2), not c1: re-capturing
    # c1 (which already holds the FULL above) must PRESERVE that snapshot, never
    # downgrade it to a 0-edge SKIPPED row — that is the GV-LW-6 fail-closed
    # doctrine (a loomweave-absent recapture is the same data-loss class as a
    # mid-capture kill), and is locked by test_capture_skipped_preserves_prior_*.
    skipped = commands.capture_snapshot(repo, commit="c2", loomweave_command="/no/such/loomweave")
    assert skipped["data"]["completeness"] == "SKIPPED"
    assert skipped["data"]["edges"] == 0
    assert skipped["enrichment"]["edges"] == "skipped"


def test_gv_lw_4_truncated_neighborhood_is_delta_never_full(tmp_path: Path) -> None:
    repo = _git_repo(tmp_path)
    with _store(repo) as store:
        repo_id = store.ensure_repo(repo)
        _seed_entity(store, repo_id, "python:function:pkg/mod.py::a", None)
        result = capture_edge_snapshot(
            store, repo, commit_sha="c1", client=_TruncatedNeighborhoodClient(), source_version="t"
        )
    assert result["completeness"] == "DELTA"
    assert result["completeness"] != "FULL"


def test_gv_lw_5_sei_resolution_present_vs_unavailable(tmp_path: Path) -> None:
    repo = _git_repo(tmp_path)
    # resolved → enrichment.sei present
    with _store(repo) as store:
        repo_id = store.ensure_repo(repo)
        a = _seed_entity(store, repo_id, "python:function:m.py::f", "loomweave:eid:resolved")
        _add_change(store, repo_id, a, path="m.py")
    present = commands.change_list(repo)
    assert present["enrichment"]["sei"] == "present"

    # loomweave unreachable on capture → sei unavailable, never an implied clean state
    unavailable = commands.capture_snapshot(repo, commit="c1", loomweave_command="/no/such")
    assert unavailable["enrichment"]["sei"] == "unavailable"


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


# ============================================================ SEAM 2 — filigree
def test_gv_fi_1_reverify_enriched_with_linked_p1_issue(tmp_path: Path) -> None:
    repo = _git_repo(tmp_path)
    with _store(repo) as store:
        repo_id = store.ensure_repo(repo)
        a = _seed_entity(store, repo_id, "python:function:m.py::f", "loomweave:eid:X")
        _add_change(store, repo_id, a, path="m.py")
        key_id = a
    client = _FixtureWorkClient(
        {"loomweave:eid:X": {"id": "filigree-1", "status": "in_progress", "priority": 1}}
    )
    env = commands.reverify_worklist(repo, [key_id], work_client=client)
    item = next(i for i in env["data"]["items"] if i["entity"]["sei"] == "loomweave:eid:X")
    assert item["priority"] == "P1"
    assert item["enrichment"]["work"][0]["issue_status"] == "in_progress"
    assert env["data"]["next_actions"]["filigree"]  # candidate(s)
    assert env["enrichment"]["work"] == "present"
    # warpline filed nothing — the candidate is a proposal, not an executed action.
    assert env["data"]["next_actions"]["filigree"][0]["proposed_action"] == "review_linked_issue"
    assert env["meta"]["peer_side_effects"] == []


def test_gv_fi_2_reverify_without_filigree_is_useful_and_unavailable(tmp_path: Path) -> None:
    repo = _git_repo(tmp_path)
    with _store(repo) as store:
        repo_id = store.ensure_repo(repo)
        a = _seed_entity(store, repo_id, "python:function:m.py::f", "loomweave:eid:X")
        _add_change(store, repo_id, a, path="m.py")
        key_id = a
    env = commands.reverify_worklist(repo, [key_id], work_client=None)
    assert env["enrichment"]["work"] == "unavailable"
    assert env["data"]["items"]  # still non-empty (solo reverify)
    assert env["data"]["items"][0]["enrichment"]["work"] == []


def test_gv_fi_3_entity_association_reverse_lookup(tmp_path: Path) -> None:
    client = _FixtureWorkClient(
        {"loomweave:eid:X": {"id": "filigree-7", "status": "open", "priority": 2}}
    )
    bound = work_enrichment_for_sei(client, "loomweave:eid:X")
    assert bound and bound[0]["issue_id"] == "filigree-7"
    # a SEI with no binding → [] (not an error)
    assert work_enrichment_for_sei(client, "loomweave:eid:Y") == []


# ============================================================ SEAM 3 — wardline
def test_gv_wl_1_impact_radius_full_snapshot(tmp_path: Path) -> None:
    repo = _git_repo(tmp_path)
    head = _git(repo, ["rev-parse", "HEAD"]).strip()
    with _store(repo) as store:
        repo_id = store.ensure_repo(repo)
        a = _seed_entity(store, repo_id, "python:function:m.py::a", "loomweave:eid:aaaa")
        b = _seed_entity(store, repo_id, "python:function:m.py::b", "loomweave:eid:bbbb")
        _add_change(store, repo_id, a, path="m.py")
        snap = store.create_edge_snapshot(repo_id, head, "loomweave", "t", "FULL")
        store.append_snapshot_edge(
            snap, source_entity_key_id=a, target_entity_key_id=b, edge_kind="calls",
            confidence="resolved",
        )
        a_id = a
    env = commands.impact_radius(repo, [a_id], depth=2)
    assert env["data"]["completeness"] == "FULL"
    assert env["data"]["affected"]  # non-empty
    assert env["data"]["staleness"]["commits_behind"] == 0


def test_gv_wl_2_impact_radius_no_snapshot(tmp_path: Path) -> None:
    repo = _git_repo(tmp_path)
    with _store(repo) as store:
        repo_id = store.ensure_repo(repo)
        a = _seed_entity(store, repo_id, "python:function:m.py::a", None)
        _add_change(store, repo_id, a, path="m.py")
        a_id = a
    env = commands.impact_radius(repo, [a_id], depth=2)
    assert env["data"]["completeness"] == "NO_SNAPSHOT"
    assert env["data"]["affected"] == []
    assert env["ok"] is True  # exit 0, not an error


def test_gv_wl_3_wardline_absent_is_unavailable_never_clean(tmp_path: Path) -> None:
    repo = _git_repo(tmp_path)
    head = _git(repo, ["rev-parse", "HEAD"]).strip()
    with _store(repo) as store:
        repo_id = store.ensure_repo(repo)
        a = _seed_entity(store, repo_id, "python:function:m.py::a", "loomweave:eid:aaaa")
        b = _seed_entity(store, repo_id, "python:function:m.py::b", "loomweave:eid:bbbb")
        _add_change(store, repo_id, a, path="m.py")
        snap = store.create_edge_snapshot(repo_id, head, "loomweave", "t", "FULL")
        store.append_snapshot_edge(
            snap, source_entity_key_id=a, target_entity_key_id=b, edge_kind="calls",
            confidence="resolved",
        )
        a_id = a
    env = commands.reverify_worklist(repo, [a_id], depth=2)
    assert env["enrichment"]["risk"] == "unavailable"
    depths = [item["depth"] for item in env["data"]["items"]]
    assert depths == sorted(depths)  # ordered by depth, changed (0) first
    for item in env["data"]["items"]:
        assert item["enrichment"]["risk"] == []
        assert "clean" not in item and "allowed" not in item


# ============================================================ SEAM 4 — legis
def test_gv_lg_1_impact_radius_is_advisory_only(tmp_path: Path) -> None:
    repo = _git_repo(tmp_path)
    with _store(repo) as store:
        repo_id = store.ensure_repo(repo)
        a = _seed_entity(store, repo_id, "python:function:m.py::a", None)
        _add_change(store, repo_id, a, path="m.py")
        a_id = a
    env = commands.impact_radius(repo, [a_id], depth=2)
    assert "completeness" in env["data"] and "staleness" in env["data"]
    # advisory: warpline never claims a governance verdict / write side effect
    assert env["meta"]["local_only"] is True
    assert env["meta"]["peer_side_effects"] == []
    assert "governance_verdict" not in env["data"]


def test_gv_lg_2_timeline_stitches_across_rename_feed(tmp_path: Path) -> None:
    repo = _git_repo(tmp_path)
    old = "python:function:old_mod.py::f"
    new = "python:function:new_mod.py::f"
    with _store(repo) as store:
        repo_id = store.ensure_repo(repo)
        a = _seed_entity(store, repo_id, old, None)
        _add_change(store, repo_id, a, path="old_mod.py", commit="c1")

    feed = RenameFeed([{"old_locator": old, "new_locator": new}])
    with_feed = commands.entity_timeline(repo, new, rename_feed=feed)
    assert with_feed["data"]["items"]  # pre-rename events surface for the new locator
    assert with_feed["enrichment"]["governance"] == "present"

    # legis absent → raw-git fallback, governance unavailable, no verdict implied
    without_feed = commands.entity_timeline(repo, new)
    assert without_feed["enrichment"]["governance"] == "unavailable"


def test_gv_lg_3_every_response_is_local_only_with_no_side_effects(tmp_path: Path) -> None:
    repo = _git_repo(tmp_path)
    with _store(repo) as store:
        repo_id = store.ensure_repo(repo)
        a = _seed_entity(store, repo_id, "python:function:m.py::a", "loomweave:eid:aaaa")
        _add_change(store, repo_id, a, path="m.py")
        a_id = a
    envelopes = [
        commands.change_list(repo),
        commands.entity_timeline(repo, "python:function:m.py::a"),
        commands.entity_churn_count(repo, [{"kind": "sei", "value": "loomweave:eid:aaaa"}]),
        commands.impact_radius(repo, [a_id]),
        commands.reverify_worklist(repo, [a_id]),
        commands.capture_snapshot(repo, commit="c1", loomweave_command="/no/such"),
    ]
    for env in envelopes:
        assert env["meta"]["local_only"] is True
        assert env["meta"]["peer_side_effects"] == []


# ============================================================ honesty completeness (WS2)
def test_gv_hon_sei_sei_absence_carries_explained_triple(tmp_path: Path) -> None:
    """GV-HON-SEI: sei absence is EXPLAINED — change_list with no SEI emits
    sei:absent + unresolved_input triple; capture with Loomweave down emits
    sei:unavailable + unreachable triple. Never a bare, unexplained scalar."""

    repo = _git_repo(tmp_path)
    with _store(repo) as store:
        repo_id = store.ensure_repo(repo)
        a = _seed_entity(store, repo_id, "python:function:m.py::f", None)
        _add_change(store, repo_id, a, path="m.py")
    listed = commands.change_list(repo)
    assert listed["enrichment"]["sei"] == "absent"
    t_absent = listed["enrichment_reasons"]["sei"]
    assert t_absent["reason_class"] == "unresolved_input"
    assert t_absent["cause"]
    assert t_absent["fix"]

    captured = commands.capture_snapshot(repo, commit="c1", loomweave_command="/no/such")
    assert captured["enrichment"]["sei"] == "unavailable"
    t_unreach = captured["enrichment_reasons"]["sei"]
    assert t_unreach["reason_class"] == "unreachable"
    assert t_unreach["cause"]
    assert t_unreach["fix"]


def test_gv_hon_gov_timeline_governance_carries_explained_triple(tmp_path: Path) -> None:
    """GV-HON-GOV: entity_timeline governance is EXPLAINED — present->clean with a
    rename feed, disabled (no transport) without one."""

    repo = _git_repo(tmp_path)
    old = "python:function:old_mod.py::f"
    new = "python:function:new_mod.py::f"
    with _store(repo) as store:
        repo_id = store.ensure_repo(repo)
        a = _seed_entity(store, repo_id, old, None)
        _add_change(store, repo_id, a, path="old_mod.py", commit="c1")

    feed = RenameFeed([{"old_locator": old, "new_locator": new}])
    with_feed = commands.entity_timeline(repo, new, rename_feed=feed)
    assert with_feed["enrichment"]["governance"] == "present"
    assert with_feed["enrichment_reasons"]["governance"] == {"reason_class": "clean"}

    without_feed = commands.entity_timeline(repo, new)
    assert without_feed["enrichment"]["governance"] == "unavailable"
    t_gov_disabled = without_feed["enrichment_reasons"]["governance"]
    assert t_gov_disabled["reason_class"] == "disabled"
    assert t_gov_disabled["cause"]
    assert t_gov_disabled["fix"]


def test_gv_hon_req_requirements_is_reserved_but_honest_on_every_tool(tmp_path: Path) -> None:
    """GV-HON-REQ: the reserved requirements dimension carries a stable disabled
    triple (reserved, not yet wired) on every tool — scalar stays unavailable."""

    repo = _git_repo(tmp_path)
    with _store(repo) as store:
        repo_id = store.ensure_repo(repo)
        a = _seed_entity(store, repo_id, "python:function:m.py::a", "loomweave:eid:aaaa")
        _add_change(store, repo_id, a, path="m.py")
        a_id = a
    envelopes = [
        commands.change_list(repo),
        commands.entity_timeline(repo, "python:function:m.py::a"),
        commands.entity_churn_count(repo, [{"kind": "sei", "value": "loomweave:eid:aaaa"}]),
        commands.impact_radius(repo, [a_id]),
        commands.reverify_worklist(repo, [a_id]),
        commands.capture_snapshot(repo, commit="c1", loomweave_command="/no/such"),
    ]
    for env in envelopes:
        assert env["enrichment"]["requirements"] == "unavailable"
        triple = env["enrichment_reasons"]["requirements"]
        assert triple["reason_class"] == "disabled"
        assert triple["cause"]
        assert "reserved" in triple["cause"].lower()
        assert triple["fix"]


# ============================================================ SEAM 5 — verification freshness
def test_gv_vf_1_reverify_verification_freshness_is_explained(tmp_path: Path) -> None:
    """GV-VF-1: the reverify worklist carries an HONEST verification block.

    Locks: (a) unverified-when-no-source — every item reads ``unverified`` with a
    ``disabled`` reason when no gate pass is recorded; (b) ``fresh`` once the
    change is verified; (c) the never-filter invariant — recording verification
    annotates/sorts but never removes an item; (d) verification rides the data
    block, never the FROZEN enrichment vocab.
    """

    repo = _git_repo(tmp_path)
    # One real commit so verify-record can resolve HEAD to an object SHA.
    head = _commit_file(repo, "m.py", "v0\n")
    with _store(repo) as store:
        repo_id = store.ensure_repo(repo)
        key_id = store.ensure_entity_key(repo_id, "python:function:m.py::f", None, head)
        store.append_change_event(
            repo_id=repo_id, entity_key_id=key_id, commit_sha=head, path="m.py",
            change_kind="modified", actor="dev", changed_at="2026-06-25T08:00:00+00:00",
        )

    # (a) No verification recorded yet -> unverified + explained.
    env = commands.reverify_worklist(repo, [key_id])
    summary = env["data"]["verification_summary"]
    assert summary["local_source_configured"] is False
    assert summary["unverified"] >= 1
    assert env["data"]["items"], "expected a non-empty worklist"
    n_items = len(env["data"]["items"])
    item = env["data"]["items"][0]
    assert item["verification"]["state"] == "unverified"
    assert item["verification"]["reason"]["reason_class"] == "disabled"
    assert item["verification"]["reason"]["cause"] and item["verification"]["reason"]["fix"]
    # (d) verification is NOT in the frozen enrichment vocab.
    assert "verification" not in env["enrichment"]
    assert "verification" not in env["enrichment_reasons"]
    # Honesty meta preserved on the pre-verify envelope too.
    assert env["meta"]["local_only"] is True
    assert env["meta"]["peer_side_effects"] == []

    # (b) record a gate pass at HEAD -> fresh.
    commands.verify_record(repo, commit=head, kind="test_pass", now="2026-06-25T10:00:00+00:00")
    env2 = commands.reverify_worklist(repo, [key_id])
    assert env2["data"]["verification_summary"]["local_source_configured"] is True
    assert env2["data"]["verification_summary"]["fresh"] >= 1
    assert env2["data"]["items"], "expected a non-empty worklist after verification"
    assert any(i["reason"] == "changed" for i in env2["data"]["items"])
    fresh_item = next(i for i in env2["data"]["items"] if i["reason"] == "changed")
    assert fresh_item["verification"]["state"] == "fresh"
    assert fresh_item["verification"]["last_verified_commit"] == head

    # (c) never-filter is an IDENTITY invariant, not just cardinality: the exact
    # SET of entities is unchanged by recording verification (count-equality alone
    # would pass a buggy impl that drops one item and re-adds a different one).
    assert len(env2["data"]["items"]) == n_items
    before_locators = {i["entity"]["locator"] for i in env["data"]["items"]}
    after_locators = {i["entity"]["locator"] for i in env2["data"]["items"]}
    assert after_locators == before_locators
    # Honesty meta preserved.
    assert env2["meta"]["local_only"] is True
    assert env2["meta"]["peer_side_effects"] == []
