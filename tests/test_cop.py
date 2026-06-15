"""Rung 2 Track D — temporal COP internals (cop.py).

Locks ``resolve_frame`` per frame kind (rev_range / time_window / sei /
branch_sha / edit) and ``compose_temporal_cop``'s coverage / dark_sectors
honesty. The PUBLIC COP MCP/CLI tool is interface-pending and NOT wired here;
these test the internals only.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from conftest import commit as _commit
from conftest import init_repo as _init_repo

from warpline.cop import compose_temporal_cop, resolve_frame
from warpline.git import ingest_commit
from warpline.store import WarplineStore, default_store_path


def _seed(repo: Path, name: str, body: str) -> str:
    sha = _commit(repo, name, body)
    with WarplineStore.open(default_store_path(repo)) as store:
        ingest_commit(store, repo, sha)
    return sha


def test_resolve_frame_rev_range_resolves_items(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    sha1 = _seed(repo, "a.py", "def f():\n    return 1\n")
    sha2 = _seed(repo, "b.py", "def g():\n    return 2\n")
    with WarplineStore.open(default_store_path(repo)) as store:
        items, echo, warnings = resolve_frame(
            store, repo, {"kind": "rev_range", "rev_range": f"{sha1}..{sha2}"}
        )
    assert echo["kind"] == "rev_range"
    assert echo["weft_reason_class"] == "clean"
    assert warnings == []
    paths = {item["entity"]["path"] for item in items}
    assert "b.py" in paths


def test_resolve_frame_rev_range_vanished_shas_degrades_honestly(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    _seed(repo, "a.py", "x = 1\n")
    with WarplineStore.open(default_store_path(repo)) as store:
        # A rev-range naming SHAs that resolve to no recorded events (the
        # squash-merge collapse failure path) degrades to unresolved_input.
        items, echo, _warnings = resolve_frame(
            store,
            repo,
            {"kind": "rev_range", "rev_range": "0000000000000000000000000000000000000000..HEAD~99"},
        )
    assert items == []
    assert echo["weft_reason_class"] == "unresolved_input"
    assert echo["weft_reason"]["cause"]
    assert echo["weft_reason"]["fix"]


def test_resolve_frame_time_window(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    _seed(repo, "a.py", "x = 1\n")
    with WarplineStore.open(default_store_path(repo)) as store:
        all_events = store.list_change_events(repo)
        when = str(all_events[0]["changed_at"])
        items, echo, _ = resolve_frame(
            store, repo, {"kind": "time_window", "since": when, "until": when}
        )
        empty_items, empty_echo, _ = resolve_frame(
            store,
            repo,
            {"kind": "time_window", "since": "2099-01-01T00:00:00+00:00", "until": None},
        )
    assert echo["kind"] == "time_window"
    assert echo["weft_reason_class"] == "clean"
    assert items
    assert empty_items == []
    assert empty_echo["weft_reason_class"] == "unresolved_input"


def test_resolve_frame_sei_uses_timeline(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    _seed(repo, "a.py", "def f():\n    return 1\n")
    with WarplineStore.open(default_store_path(repo)) as store:
        events = store.list_change_events(repo)
        locator = str(events[0]["locator"])
        items, echo, _ = resolve_frame(store, repo, {"kind": "sei", "sei": locator})
        miss_items, miss_echo, _ = resolve_frame(
            store, repo, {"kind": "sei", "sei": "warpline:does-not-exist"}
        )
    assert echo["kind"] == "sei"
    assert echo["weft_reason_class"] == "clean"
    assert items
    assert miss_items == []
    assert miss_echo["weft_reason_class"] == "unresolved_input"


def test_resolve_frame_edit_uses_git_diff(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    _seed(repo, "a.py", "x = 1\n")
    # Uncommitted edit to a tracked file → git diff HEAD reports it.
    (repo / "a.py").write_text("x = 2\n", encoding="utf-8")
    with WarplineStore.open(default_store_path(repo)) as store:
        items, echo, _ = resolve_frame(store, repo, {"kind": "edit", "rev": "HEAD"})
    assert echo["kind"] == "edit"
    assert "a.py" in echo["diff_paths"]
    # The edited path matches a recorded change event → clean resolution.
    assert echo["weft_reason_class"] == "clean"
    assert any(item["entity"]["path"] == "a.py" for item in items)


def test_resolve_frame_edit_clean_tree_is_unresolved_input(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    _seed(repo, "a.py", "x = 1\n")
    with WarplineStore.open(default_store_path(repo)) as store:
        items, echo, _ = resolve_frame(store, repo, {"kind": "edit", "rev": "HEAD"})
    assert items == []
    assert echo["weft_reason_class"] == "unresolved_input"


def test_resolve_frame_branch_sha_emits_fallback_warning(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    _seed(repo, "base.py", "BASE = 0\n")
    sha = _seed(repo, "a.py", "x = 1\n")  # has a parent → sha~1..sha is valid
    with WarplineStore.open(default_store_path(repo)) as store:
        items, echo, warnings = resolve_frame(
            store, repo, {"kind": "branch_sha", "branch": "main", "sha": sha}
        )
    assert echo["kind"] == "branch_sha"
    assert echo["weft_reason_class"] == "partial"
    assert any("fell back" in w for w in warnings)
    assert echo["fallback_rev_range"] == f"{sha}~1..{sha}"
    assert items


def test_resolve_frame_unknown_kind_is_rejected(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    with WarplineStore.open(default_store_path(repo)) as store:
        items, echo, _ = resolve_frame(store, repo, {"kind": "nonsense"})
    assert items == []
    assert echo["weft_reason_class"] == "rejected"


def test_compose_temporal_cop_lists_every_member_as_dark_sector(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    _seed(repo, "a.py", "def f():\n    return 1\n")
    with WarplineStore.open(default_store_path(repo)) as store:
        items, echo, _ = resolve_frame(store, repo, {"kind": "rev_range", "rev_range": None})
    # No transports wired → all three members are dark sectors (disabled),
    # NEVER silently dropped to look like a clean empty.
    cop = compose_temporal_cop(items, echo)
    assert set(cop["members"]) == {"filigree", "wardline", "legis"}
    coverage = cop["coverage"]
    assert coverage["members_total"] == 3
    assert coverage["members_consulted"] == 0
    dark = {d["member"] for d in coverage["dark_sectors"]}
    assert dark == {"filigree", "wardline", "legis"}
    for sector in coverage["dark_sectors"]:
        assert sector["reason_class"] == "disabled"
        assert sector["cause"] and sector["fix"]
    assert cop["frame"] is echo


class _StubWork:
    """Reachable filigree transport that returns associations for any SEI."""

    def associations(self, sei: str) -> list[dict[str, Any]]:
        return [{"issue_id": "WL-1", "sei": sei}]


def test_compose_temporal_cop_consulted_member_is_not_dark(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    _seed(repo, "a.py", "def f():\n    return 1\n")
    with WarplineStore.open(default_store_path(repo)) as store:
        events = store.list_change_events(repo)
        # Force a SEI onto the item so the filigree consult has something to read.
        items, echo, _ = resolve_frame(store, repo, {"kind": "rev_range", "rev_range": None})
    for item in items:
        item["entity"]["sei"] = "loomweave:eid:demo"
    cop = compose_temporal_cop(items, echo, work_client=_StubWork())
    assert cop["members"]["filigree"]["weft_reason"]["reason_class"] == "clean"
    dark = {d["member"] for d in cop["coverage"]["dark_sectors"]}
    assert "filigree" not in dark
    assert dark == {"wardline", "legis"}
    assert cop["coverage"]["members_consulted"] == 1
    assert events  # sanity: events were ingested
