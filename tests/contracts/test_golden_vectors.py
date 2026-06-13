"""The 14 FROZEN golden vectors (interface-lock §1D, 2C, 3C, 4C).

These are heddle's contribution as the 5th producer to the four-member
conformance oracle (GS-7). Each test is one frozen (input → output assertion)
vector; the GV id in the name maps 1:1 to the spec table.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from heddle import commands
from heddle.siblings import RenameFeed, work_enrichment_for_sei
from heddle.snapshot import capture_edge_snapshot
from heddle.store import HeddleStore, default_store_path

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


def _store(repo: Path) -> HeddleStore:
    return HeddleStore.open(default_store_path(repo))


def _seed_entity(
    store: HeddleStore, repo_id: str, locator: str, sei: str | None, commit: str = "c1"
) -> int:
    return store.ensure_entity_key(repo_id, locator=locator, sei=sei, commit_sha=commit)


def _add_change(
    store: HeddleStore,
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
    assert "heddle_reverify_worklist_get" in env["next_actions"]
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

    skipped = commands.capture_snapshot(repo, commit="c1", loomweave_command="/no/such/loomweave")
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
    # heddle filed nothing — the candidate is a proposal, not an executed action.
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
    # advisory: heddle never claims a governance verdict / write side effect
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
