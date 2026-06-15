"""G2 — list-ergonomics microaffordances are FULLY HONORED.

Every advertised read-tool knob (filters / sort_by / sort_order / cursor /
group_by) does what an agent would expect: a sort actually sorts, a cursor
actually paginates, a filter actually filters, group_by actually groups, and an
oversized result spills the FULL list to a file at project root with a warning
rather than silently truncating or flooding the caller. The cross-member seam
affordance ``include_federation`` is now RE-ADDED and WIRED (hub-blessed): the
inputSchema-consumption guard treats it as consumed (not parked dead), so the
fast-follow-dead set stays EMPTY for every tool.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from warpline import commands
from warpline.errors import InvalidFilterError, InvalidSortError
from warpline.listing import OVERFLOW_THRESHOLD, REASON_CLASSES, reason
from warpline.mcp import _KNOWN_FASTFOLLOW_DEAD, TOOL_SPECS, assert_inputschema_consumed, dispatch
from warpline.store import WarplineStore, default_store_path


# --------------------------------------------------------------------------- fixtures
def _seed_changes(repo: Path, rows: list[dict[str, str]]) -> None:
    """Seed change_events directly so list shaping is exercised deterministically.

    Each row: {locator, sei?, commit, path, change_kind, actor, changed_at}.
    """

    with WarplineStore.open(default_store_path(repo)) as store:
        repo_id = store.ensure_repo(repo)
        for row in rows:
            key_id = store.ensure_entity_key(
                repo_id, locator=row["locator"], sei=row.get("sei"), commit_sha=row["commit"]
            )
            store.append_change_event(
                repo_id=repo_id,
                entity_key_id=key_id,
                commit_sha=row["commit"],
                path=row["path"],
                change_kind=row["change_kind"],
                actor=row["actor"],
                changed_at=row["changed_at"],
            )


def _three_changes(repo: Path) -> None:
    _seed_changes(
        repo,
        [
            {
                "locator": "python:function:a",
                "sei": "loomweave:eid:a",
                "commit": "c1",
                "path": "src/a.py",
                "change_kind": "added",
                "actor": "agent:alice",
                "changed_at": "2026-06-01T00:00:00Z",
            },
            {
                "locator": "python:function:b",
                "commit": "c2",
                "path": "src/b.py",
                "change_kind": "modified",
                "actor": "agent:bob",
                "changed_at": "2026-06-02T00:00:00Z",
            },
            {
                "locator": "python:function:c",
                "commit": "c3",
                "path": "lib/c.py",
                "change_kind": "modified",
                "actor": "agent:alice",
                "changed_at": "2026-06-03T00:00:00Z",
            },
        ],
    )


# --------------------------------------------------------------------------- filters
def test_change_list_filter_by_actor_actually_filters(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _three_changes(repo)
    env = commands.change_list(repo, filters={"actor": "agent:alice"})
    actors = {i["actor"] for i in env["data"]["items"]}
    assert actors == {"agent:alice"}
    assert len(env["data"]["items"]) == 2
    # the active filter is echoed into the query block (self-describing scope)
    assert env["query"]["filters"] == {"actor": "agent:alice"}


def test_change_list_filter_by_path_prefix(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _three_changes(repo)
    env = commands.change_list(repo, filters={"path_prefix": "src/"})
    paths = {i["entity"]["path"] for i in env["data"]["items"]}
    assert paths == {"src/a.py", "src/b.py"}


def test_change_list_filter_has_sei(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _three_changes(repo)
    env = commands.change_list(repo, filters={"has_sei": True})
    seis = [i["entity"]["sei"] for i in env["data"]["items"]]
    assert seis == ["loomweave:eid:a"]


def test_change_list_filter_since_until_window(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _three_changes(repo)
    env = commands.change_list(
        repo, filters={"since": "2026-06-02T00:00:00Z", "until": "2026-06-02T23:59:59Z"}
    )
    assert {i["commit"] for i in env["data"]["items"]} == {"c2"}


def test_unknown_filter_key_rejects_loudly(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _three_changes(repo)
    with pytest.raises(InvalidFilterError, match="unrecognised filter key"):
        commands.change_list(repo, filters={"nonsense": "x"})


# --------------------------------------------------------------------------- sort
def test_change_list_sort_by_path_actually_sorts(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _three_changes(repo)
    asc = commands.change_list(repo, sort_by="path", sort_order="asc")
    paths = [i["entity"]["path"] for i in asc["data"]["items"]]
    assert paths == sorted(paths)
    assert paths[0] == "lib/c.py"
    desc = commands.change_list(repo, sort_by="path", sort_order="desc")
    assert [i["entity"]["path"] for i in desc["data"]["items"]] == list(reversed(paths))


def test_unknown_sort_by_rejects_loudly(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _three_changes(repo)
    with pytest.raises(InvalidSortError, match="unrecognised sort_by"):
        commands.change_list(repo, sort_by="bogus")


def test_bad_sort_order_rejects_loudly(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _three_changes(repo)
    with pytest.raises(InvalidSortError, match="sort_order"):
        commands.change_list(repo, sort_by="path", sort_order="sideways")


# --------------------------------------------------------------------------- cursor
def test_cursor_actually_paginates_a_full_pass(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _three_changes(repo)

    page1 = commands.change_list(repo, sort_by="path", sort_order="asc", limit=2)
    assert len(page1["data"]["items"]) == 2
    assert page1["data"]["page"]["has_more"] is True
    cursor = page1["data"]["page"]["next_cursor"]
    assert cursor is not None

    page2 = commands.change_list(
        repo, sort_by="path", sort_order="asc", limit=2, cursor=cursor
    )
    assert len(page2["data"]["items"]) == 1
    assert page2["data"]["page"]["has_more"] is False
    assert page2["data"]["page"]["next_cursor"] is None

    # The two pages, concatenated, are the full ordered set with no overlap/gap.
    seen = [i["entity"]["path"] for i in page1["data"]["items"]] + [
        i["entity"]["path"] for i in page2["data"]["items"]
    ]
    assert seen == ["lib/c.py", "src/a.py", "src/b.py"]


def test_cursor_past_end_is_honest_partial_not_silent_clean(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _three_changes(repo)
    env = commands.change_list(repo, limit=2, cursor="warpline:cursor:99")
    page = env["data"]["page"]
    assert env["data"]["items"] == []
    assert page["reason_class"] == "partial"
    assert "cause" in page and "fix" in page


def test_malformed_cursor_rejects_loudly(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _three_changes(repo)
    with pytest.raises(InvalidSortError, match="cursor"):
        commands.change_list(repo, cursor="not-a-warpline-cursor")


def test_clean_page_carries_clean_reason(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _three_changes(repo)
    env = commands.change_list(repo)
    assert env["data"]["page"]["reason_class"] == "clean"
    assert "cause" not in env["data"]["page"]


# --------------------------------------------------------------------------- group_by
def _reverify_with_many_items(repo: Path, n: int) -> dict:
    rows = []
    for i in range(n):
        rows.append(
            {
                "locator": f"python:function:e{i}",
                "commit": f"c{i}",
                "path": f"src/mod{i % 2}.py",
                "change_kind": "modified",
                "actor": "agent:alice",
                "changed_at": f"2026-06-{(i % 28) + 1:02d}T00:00:00Z",
            }
        )
    _seed_changes(repo, rows)
    key_ids = list(range(1, n + 1))
    return commands.reverify_worklist(repo, key_ids, depth=2, rev_range=None)


def test_reverify_group_by_file_actually_groups(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    # Representative locators embed the file path (as backfill mints them), so
    # group_by:file recovers the path from the locator the worklist entity carries.
    _seed_changes(
        repo,
        [
            {
                "locator": "python:function:src/x.py::a",
                "commit": "c1",
                "path": "src/x.py",
                "change_kind": "modified",
                "actor": "agent:alice",
                "changed_at": "2026-06-01T00:00:00Z",
            },
            {
                "locator": "python:function:src/x.py::b",
                "commit": "c2",
                "path": "src/x.py",
                "change_kind": "modified",
                "actor": "agent:bob",
                "changed_at": "2026-06-02T00:00:00Z",
            },
            {
                "locator": "python:function:src/y.py::c",
                "commit": "c3",
                "path": "src/y.py",
                "change_kind": "modified",
                "actor": "agent:alice",
                "changed_at": "2026-06-03T00:00:00Z",
            },
        ],
    )
    env = commands.reverify_worklist(repo, [1, 2, 3], depth=2, group_by="file")
    grouped = env["data"]["grouped"]
    assert set(grouped) == {"src/x.py", "src/y.py"}
    assert len(grouped["src/x.py"]) == 2
    assert len(grouped["src/y.py"]) == 1
    assert env["query"]["group_by"] == "file"


def test_reverify_group_by_none_returns_no_buckets(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _three_changes(repo)
    env = commands.reverify_worklist(repo, [1, 2, 3], depth=2, group_by="none")
    assert env["data"]["grouped"] is None


def test_reverify_unknown_group_by_rejects_loudly(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _three_changes(repo)
    with pytest.raises(InvalidSortError, match="unrecognised group_by"):
        commands.reverify_worklist(repo, [1, 2, 3], depth=2, group_by="galaxy")


# --------------------------------------------------------------------------- overflow
def test_oversized_result_dumps_full_list_to_file_with_warning(tmp_path: Path) -> None:
    """An oversized list spills the FULL set to a file at project root, warns,
    and rides only the lead window in-band — never a silent truncation."""

    repo = tmp_path / "repo"
    repo.mkdir()
    n = OVERFLOW_THRESHOLD + 5
    rows = [
        {
            "locator": f"python:function:e{i}",
            "commit": f"c{i}",
            "path": f"src/e{i}.py",
            "change_kind": "modified",
            "actor": "agent:alice",
            "changed_at": f"2026-06-01T00:00:{i % 60:02d}Z",
        }
        for i in range(n)
    ]
    _seed_changes(repo, rows)

    env = commands.change_list(repo, limit=1000)
    overflow = env["data"]["overflow"]
    assert overflow["total"] == n
    assert overflow["returned"] == OVERFLOW_THRESHOLD
    assert overflow["reason_class"] == "partial"
    assert len(env["data"]["items"]) == OVERFLOW_THRESHOLD
    assert any(w.startswith("OVERFLOW:") for w in env["warnings"])

    dump = Path(overflow["dumped_to"])
    assert dump.exists()
    assert str(dump).startswith(str(repo.resolve()))
    payload = json.loads(dump.read_text(encoding="utf-8"))
    assert payload["total"] == n
    assert len(payload["items"]) == n


def test_under_threshold_writes_no_file_and_is_clean(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _three_changes(repo)
    env = commands.change_list(repo)
    overflow = env["data"]["overflow"]
    assert overflow["reason_class"] == "clean"
    assert overflow["dumped_to"] is None
    assert not (repo.resolve() / ".weft" / "warpline" / "overflow").exists()


# ------------------------------------------------------------------ base/head + next_actions
def test_include_next_actions_false_suppresses_next_actions(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _three_changes(repo)
    on = commands.change_list(repo, include_next_actions=True)
    off = commands.change_list(repo, include_next_actions=False)
    assert "warpline_reverify_worklist_get" in on["next_actions"]
    assert off["next_actions"] == {}


def test_base_head_ref_conflicts_with_rev_range(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _three_changes(repo)
    with pytest.raises(Exception, match="rev_range OR base_ref"):
        commands.change_list(repo, rev_range="HEAD~1..HEAD", base_ref="x", head_ref="y")


# --------------------------------------------------------------------------- impact sort/filter
def test_impact_sort_and_filter_on_affected(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    head = "c1"
    with WarplineStore.open(default_store_path(repo)) as store:
        repo_id = store.ensure_repo(repo)
        a = store.ensure_entity_key(repo_id, locator="python:function:a", sei=None, commit_sha=head)
        b = store.ensure_entity_key(repo_id, locator="python:function:b", sei=None, commit_sha=head)
        c = store.ensure_entity_key(repo_id, locator="python:function:c", sei=None, commit_sha=head)
        snap = store.create_edge_snapshot(repo_id, head, "loomweave", "test", "FULL")
        store.append_snapshot_edge(
            snap, source_entity_key_id=a, target_entity_key_id=b,
            edge_kind="calls", confidence="resolved",
        )
        store.append_snapshot_edge(
            snap, source_entity_key_id=b, target_entity_key_id=c,
            edge_kind="imports", confidence="heuristic",
        )
    env = commands.impact_radius(repo, [a], depth=3, sort_by="depth", sort_order="desc")
    depths = [row["depth"] for row in env["data"]["affected"]]
    assert depths == sorted(depths, reverse=True)
    # filter by edge_kind keeps only affected rows reached via a calls edge
    filtered = commands.impact_radius(repo, [a], depth=3, filters={"edge_kind": "calls"})
    kinds = {
        e["kind"] for row in filtered["data"]["affected"] for e in row["via_edges"]
    }
    assert "imports" not in kinds or all(
        any(e["kind"] == "calls" for e in row["via_edges"])
        for row in filtered["data"]["affected"]
    )


# ------------------------------------------------------------------ enforce guard + seam wiring
def test_include_federation_is_advertised_and_consumed() -> None:
    """The cross-member seam knob is RE-ADDED to the schema AND declared consumed
    by the handler (a kept promise, not re-advertised-dead)."""

    from warpline import mcp

    reverify = next(
        s for s in TOOL_SPECS if s["endorsed"] == "warpline_reverify_worklist_get"
    )
    assert "include_federation" in reverify["inputSchema"]["properties"]
    assert "include_federation" in mcp._HANDLER_CONSUMES["warpline_reverify_worklist_get"]
    # ...and it is NOT parked as a dead fast-follow field.
    assert "include_federation" not in _KNOWN_FASTFOLLOW_DEAD["warpline_reverify_worklist_get"]


def test_fastfollow_dead_set_is_empty_for_every_tool() -> None:
    """Everything is wired: no advertised-but-dead field remains anywhere."""

    for tool, dead in _KNOWN_FASTFOLLOW_DEAD.items():
        assert dead == frozenset(), f"{tool} still parks dead fields: {sorted(dead)}"


def test_guard_covers_all_tools_and_passes() -> None:
    assert_inputschema_consumed()
    consumes_names = {s["endorsed"] for s in TOOL_SPECS}
    from warpline import mcp

    assert set(mcp._HANDLER_CONSUMES) == consumes_names


def test_guard_raises_on_a_poisoned_phantom_field_on_a_read_tool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The guard is live for the READ tools too (not just capture): a phantom
    field on change_list must halt startup."""

    from warpline import mcp

    poisoned = []
    for spec in mcp.TOOL_SPECS:
        spec = dict(spec)
        if spec["endorsed"] == "warpline_change_list":
            schema = {**spec["inputSchema"]}
            schema["properties"] = {**schema["properties"], "phantom_sort": {"type": "string"}}
            spec["inputSchema"] = schema
        poisoned.append(spec)
    monkeypatch.setattr(mcp, "TOOL_SPECS", poisoned)
    with pytest.raises(AssertionError, match="phantom_sort"):
        mcp.assert_inputschema_consumed()


# --------------------------------------------------------------------------- weft-reason carrier
def test_reason_clean_omits_cause_and_fix() -> None:
    assert reason("clean") == {"reason_class": "clean"}


def test_reason_nonclean_requires_cause_and_fix() -> None:
    carrier = reason("partial", cause="capped", fix="raise the cap")
    assert carrier == {"reason_class": "partial", "cause": "capped", "fix": "raise the cap"}
    with pytest.raises(AssertionError):
        reason("partial")  # missing cause/fix


def test_reason_classes_are_the_canonical_eleven() -> None:
    assert len(REASON_CLASSES) == 11
    assert "scheme_mismatch" in REASON_CLASSES and "misrouted" in REASON_CLASSES


# --------------------------------------------------------------------------- MCP wire
def test_mcp_reverify_inputschema_advertises_include_federation() -> None:
    response = dispatch({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})
    tools = response["result"]["tools"]
    reverify = next(t for t in tools if t["name"] == "warpline_reverify_worklist_get")
    assert "include_federation" in reverify["inputSchema"]["properties"]
    assert reverify["inputSchema"]["properties"]["include_federation"]["type"] == "boolean"
    assert "filters" in reverify["inputSchema"]["properties"]
    assert "group_by" in reverify["inputSchema"]["properties"]
