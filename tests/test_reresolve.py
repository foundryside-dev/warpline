"""Rung 1c — self-healing SEI re-resolution sweep.

Covers the store merge core (``reresolve_entity_key_sei`` / ``null_sei_entity_keys``)
and the orchestration sweep (``reresolve.sweep_reresolve_sei``):

- a null-sei key heals to ``resolved`` when loomweave returns a SEI;
- the twin-collision merge (with and without a colliding change_event), where
  the resolved-keyed row is canonical (M5) and the orphan null key is dropped,
  the survivor keeps the resolved SEI and the merged first/last seen;
- the M5 differing-``hunk_summary`` case — the resolved row's data is preserved;
- a double run is a convergent no-op;
- loomweave absent → zero rows mutated, posture ``unavailable``, never
  resolved-to-null.
"""

from __future__ import annotations

from pathlib import Path

from warpline.reresolve import sweep_reresolve_sei
from warpline.store import WarplineStore


class _SeiClient:
    """Fake loomweave client resolving every locator to a fixed SEI."""

    def __init__(self, sei: str = "loomweave:eid:resolved") -> None:
        self.sei = sei
        self.calls = 0

    def call_tool(self, name: str, arguments: dict[str, object]) -> dict[str, object]:
        assert name == "entity_resolve"
        self.calls += 1
        qualnames = arguments["qualnames"]
        assert isinstance(qualnames, list) and qualnames
        return {
            "results": [
                {
                    "qualname": qualnames[0],
                    "result_kind": "resolved",
                    "candidates": [{"id": "python:function:x", "sei": self.sei}],
                }
            ]
        }


class _NullClient:
    """Fake loomweave client that resolves nothing (no SEI in the index yet)."""

    def call_tool(self, name: str, arguments: dict[str, object]) -> dict[str, object]:
        return {"results": []}


_LOCATOR = "python:function:src/pkg/mod.py::fn"
_LOCATOR_B = "python:function:src/pkg/mod.py::other"


def _open(tmp_path: Path) -> WarplineStore:
    return WarplineStore.open(tmp_path / "warpline.db")


def _null_key(store: WarplineStore, repo_id: str, locator: str, commit: str) -> int:
    return store.ensure_entity_key(repo_id, locator=locator, sei=None, commit_sha=commit)


def test_null_sei_entity_keys_lists_only_null_rows_id_ordered(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    with _open(tmp_path) as store:
        repo_id = store.ensure_repo(repo)
        _null_key(store, repo_id, _LOCATOR, "c1")
        store.ensure_entity_key(repo_id, locator=_LOCATOR_B, sei="loomweave:eid:x", commit_sha="c1")
        _null_key(store, repo_id, "python:function:src/pkg/mod.py::third", "c1")

        rows = store.null_sei_entity_keys(repo)
        locators = [r["locator"] for r in rows]
        assert locators == [_LOCATOR, "python:function:src/pkg/mod.py::third"]
        assert rows[0]["id"] < rows[1]["id"]


def test_sweep_resolves_null_key_in_place(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    client = _SeiClient()
    with _open(tmp_path) as store:
        repo_id = store.ensure_repo(repo)
        key_id = _null_key(store, repo_id, _LOCATOR, "c1")

        report = sweep_reresolve_sei(store, repo, client)
        assert report == {
            "scanned": 1,
            "resolved": 1,
            "merged": 0,
            "still_null": 0,
            "loomweave": "present",
        }
        keys = {int(k["id"]): k for k in store.list_entity_keys(repo)}
        assert keys[key_id]["sei"] == "loomweave:eid:resolved"


def test_sweep_loomweave_absent_is_noop_and_unavailable(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    with _open(tmp_path) as store:
        repo_id = store.ensure_repo(repo)
        key_id = _null_key(store, repo_id, _LOCATOR, "c1")

        report = sweep_reresolve_sei(store, repo, client=None)
        assert report == {
            "scanned": 1,
            "resolved": 0,
            "merged": 0,
            "still_null": 1,
            "loomweave": "unavailable",
        }
        # Never resolved-to-null: the row is untouched, sei still NULL.
        keys = {int(k["id"]): k for k in store.list_entity_keys(repo)}
        assert keys[key_id]["sei"] is None


def test_sweep_resolves_nothing_when_index_has_no_sei(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    with _open(tmp_path) as store:
        repo_id = store.ensure_repo(repo)
        _null_key(store, repo_id, _LOCATOR, "c1")

        report = sweep_reresolve_sei(store, repo, _NullClient())
        assert report["loomweave"] == "absent"
        assert report["resolved"] == 0
        assert report["still_null"] == 1


def test_twin_collision_merges_without_duplicate_event(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    resolved_sei = "loomweave:eid:resolved"
    with _open(tmp_path) as store:
        repo_id = store.ensure_repo(repo)
        # Resolved twin exists first (commit c2), then a null-keyed row for the
        # same locator (commit c1) — minted while loomweave was down.
        twin_id = store.ensure_entity_key(
            repo_id, locator=_LOCATOR, sei=resolved_sei, commit_sha="c2"
        )
        null_id = _null_key(store, repo_id, _LOCATOR, "c1")
        # A change_event on the null key that does NOT collide with the twin.
        store.append_change_event(
            repo_id=repo_id,
            entity_key_id=null_id,
            commit_sha="c1",
            path="src/pkg/mod.py",
            change_kind="modified",
            actor="agent",
            changed_at="2026-01-01T00:00:00Z",
        )

        report = sweep_reresolve_sei(store, repo, _SeiClient(resolved_sei))
        assert report["merged"] == 1
        assert report["resolved"] == 0

        keys = {int(k["id"]): k for k in store.list_entity_keys(repo)}
        # Orphan null key gone; twin survives with the resolved SEI.
        assert null_id not in keys
        assert keys[twin_id]["sei"] == resolved_sei
        # Carried first/last seen: min(first)=c1, max(last)=c2.
        assert keys[twin_id]["first_seen_commit"] == "c1"
        assert keys[twin_id]["last_seen_commit"] == "c2"
        # The non-colliding event was repointed onto the survivor.
        events = store.list_change_events(repo)
        assert len(events) == 1
        assert int(events[0]["entity_key_id"]) == twin_id


def test_twin_collision_drops_null_keyed_duplicate_preserving_resolved_data(
    tmp_path: Path,
) -> None:
    """M5/Q7: colliding change_events keep the resolved-keyed row's data."""

    repo = tmp_path / "repo"
    resolved_sei = "loomweave:eid:resolved"
    common = dict(
        commit_sha="c1",
        path="src/pkg/mod.py",
        change_kind="modified",
        actor="agent",
        changed_at="2026-01-01T00:00:00Z",
    )
    with _open(tmp_path) as store:
        repo_id = store.ensure_repo(repo)
        twin_id = store.ensure_entity_key(
            repo_id, locator=_LOCATOR, sei=resolved_sei, commit_sha="c1"
        )
        null_id = _null_key(store, repo_id, _LOCATOR, "c1")
        # Two events that collide on the change_events UNIQUE constraint
        # (same commit/path/change_kind), differing only on hunk_summary.
        store.append_change_event(
            repo_id=repo_id, entity_key_id=twin_id, hunk_summary="RESOLVED-DATA", **common
        )
        store.append_change_event(
            repo_id=repo_id, entity_key_id=null_id, hunk_summary="NULL-DATA", **common
        )

        report = sweep_reresolve_sei(store, repo, _SeiClient(resolved_sei))
        assert report["merged"] == 1

        events = store.list_change_events(repo)
        assert len(events) == 1, "null-keyed duplicate must be deleted"
        assert int(events[0]["entity_key_id"]) == twin_id
        # The resolved-keyed row's data survives; the null row's was discarded.
        keys = {int(k["id"]): k for k in store.list_entity_keys(repo)}
        assert null_id not in keys
        # Re-read the surviving event's hunk_summary directly.
        row = store.conn.execute(
            "SELECT hunk_summary FROM change_events WHERE entity_key_id = ?",
            (twin_id,),
        ).fetchone()
        assert row["hunk_summary"] == "RESOLVED-DATA"


def test_double_run_is_a_noop(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    client = _SeiClient()
    with _open(tmp_path) as store:
        repo_id = store.ensure_repo(repo)
        _null_key(store, repo_id, _LOCATOR, "c1")

        first = sweep_reresolve_sei(store, repo, client)
        assert first["resolved"] == 1

        second = sweep_reresolve_sei(store, repo, client)
        assert second == {
            "scanned": 0,
            "resolved": 0,
            "merged": 0,
            "still_null": 0,
            "loomweave": "absent",
        }


def test_merge_core_action_noop_when_already_healed(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    with _open(tmp_path) as store:
        repo_id = store.ensure_repo(repo)
        key_id = store.ensure_entity_key(
            repo_id, locator=_LOCATOR, sei="loomweave:eid:resolved", commit_sha="c1"
        )
        # Calling the merge core on an already-resolved key matches no null row.
        outcome = store.reresolve_entity_key_sei(
            repo_id=repo_id,
            null_key_id=key_id,
            locator=_LOCATOR,
            resolved_sei="loomweave:eid:resolved",
        )
        assert outcome == {"action": "noop"}
