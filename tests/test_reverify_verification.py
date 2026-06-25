from __future__ import annotations

import subprocess
from pathlib import Path

from warpline import commands
from warpline.store import WarplineStore, default_store_path


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, text=True, capture_output=True
    ).stdout.strip()


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "r"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    return repo


def _commit(repo: Path, name: str, body: str) -> str:
    (repo / name).write_text(body)
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", f"touch {name}")
    return _git(repo, "rev-parse", "HEAD")


def _seed_entity_change(store: WarplineStore, repo: Path, locator: str, commit_sha: str) -> int:
    repo_id = store.ensure_repo(repo)
    key_id = store.ensure_entity_key(repo_id, locator, None, commit_sha)
    store.append_change_event(
        repo_id=repo_id,
        entity_key_id=key_id,
        commit_sha=commit_sha,
        path="m.py",
        change_kind="modified",
        actor="dev",
        changed_at="2026-06-25T08:00:00+00:00",
    )
    return key_id


def test_each_item_carries_a_verification_block(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    c0 = _commit(repo, "m.py", "v0\n")
    with WarplineStore.open(default_store_path(repo)) as store:
        key_id = _seed_entity_change(store, repo, "python:function:m.py::f", c0)
    env = commands.reverify_worklist(repo, [key_id])
    items = env["data"]["items"]
    assert items, "expected a non-empty worklist"
    for item in items:
        assert "verification" in item
        assert item["verification"]["state"] in {"fresh", "stale", "unverified", "unavailable"}
        assert "reason_class" in item["verification"]["reason"]


def test_unverified_when_no_verification_recorded(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    c0 = _commit(repo, "m.py", "v0\n")
    with WarplineStore.open(default_store_path(repo)) as store:
        key_id = _seed_entity_change(store, repo, "python:function:m.py::f", c0)
    env = commands.reverify_worklist(repo, [key_id])
    summary = env["data"]["verification_summary"]
    assert summary["local_source_configured"] is False
    assert summary["unverified"] >= 1
    item = env["data"]["items"][0]
    assert item["verification"]["state"] == "unverified"
    assert item["verification"]["reason"]["reason_class"] == "disabled"


def test_fresh_when_change_is_verified(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    c0 = _commit(repo, "m.py", "v0\n")
    with WarplineStore.open(default_store_path(repo)) as store:
        key_id = _seed_entity_change(store, repo, "python:function:m.py::f", c0)
    commands.verify_record(repo, commit=c0, kind="test_pass", now="2026-06-25T10:00:00+00:00")
    env = commands.reverify_worklist(repo, [key_id])
    summary = env["data"]["verification_summary"]
    assert summary["local_source_configured"] is True
    assert summary["fresh"] >= 1
    assert any(i["reason"] == "changed" for i in env["data"]["items"]), (
        "expected at least one 'changed' item"
    )
    item = next(i for i in env["data"]["items"] if i["reason"] == "changed")
    assert item["verification"]["state"] == "fresh"
    assert item["verification"]["last_verified_commit"] == c0


def test_stale_when_change_lands_after_verification(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    c0 = _commit(repo, "m.py", "v0\n")
    # Verify at c0, THEN the entity changes again at c1 (uncovered).
    commands.verify_record(repo, commit=c0, kind="test_pass", now="2026-06-25T10:00:00+00:00")
    c1 = _commit(repo, "m.py", "v1\n")
    with WarplineStore.open(default_store_path(repo)) as store:
        repo_id = store.ensure_repo(repo)
        key_id = store.ensure_entity_key(repo_id, "python:function:m.py::f", None, c0)
        for sha in (c0, c1):
            store.append_change_event(
                repo_id=repo_id, entity_key_id=key_id, commit_sha=sha, path="m.py",
                change_kind="modified", actor="dev", changed_at="2026-06-25T08:00:00+00:00",
            )
    env = commands.reverify_worklist(repo, [key_id])
    assert any(i["reason"] == "changed" for i in env["data"]["items"]), (
        "expected at least one 'changed' item"
    )
    item = next(i for i in env["data"]["items"] if i["reason"] == "changed")
    assert item["verification"]["state"] == "stale"
    assert env["data"]["verification_summary"]["stale"] >= 1


def test_verification_never_filters_items(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    c0 = _commit(repo, "m.py", "v0\n")
    with WarplineStore.open(default_store_path(repo)) as store:
        key_id = _seed_entity_change(store, repo, "python:function:m.py::f", c0)
    baseline = commands.reverify_worklist(repo, [key_id])
    n_before = len(baseline["data"]["items"])
    # Recording verification must never REMOVE an item — only annotate/sort.
    commands.verify_record(repo, commit=c0, kind="test_pass")
    after = commands.reverify_worklist(repo, [key_id])
    assert len(after["data"]["items"]) == n_before


def test_envelope_stays_local_only(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    c0 = _commit(repo, "m.py", "v0\n")
    with WarplineStore.open(default_store_path(repo)) as store:
        key_id = _seed_entity_change(store, repo, "python:function:m.py::f", c0)
    env = commands.reverify_worklist(repo, [key_id])
    assert env["meta"]["local_only"] is True
    assert env["meta"]["peer_side_effects"] == []
    # verification must NOT have leaked into the frozen enrichment vocab.
    assert "verification" not in env["enrichment"]
    assert "verification" not in env["enrichment_reasons"]


def test_verification_summary_is_post_filter_zero_case(tmp_path: Path) -> None:
    # Our entity has sei=None; filtering has_sei -> empty set -> all-zero summary.
    repo = _repo(tmp_path)
    c0 = _commit(repo, "m.py", "v0\n")
    with WarplineStore.open(default_store_path(repo)) as store:
        key_id = _seed_entity_change(store, repo, "python:function:m.py::f", c0)
    env = commands.reverify_worklist(repo, [key_id], filters={"has_sei": True})
    assert env["data"]["items"] == []
    summary = env["data"]["verification_summary"]
    assert summary["fresh"] == 0
    assert summary["stale"] == 0
    assert summary["unverified"] == 0
    assert summary["unavailable"] == 0


def test_verification_summary_counts_only_filtered_subset(tmp_path: Path) -> None:
    # Two entities; one HAS an sei, one does not. Filtering has_sei=True keeps
    # exactly ONE. The summary must count 1, not 2 — proving it is computed on the
    # POST-filter set (a pre-filter computation would report 2).
    repo = _repo(tmp_path)
    c0 = _commit(repo, "m.py", "v0\n")
    with WarplineStore.open(default_store_path(repo)) as store:
        repo_id = store.ensure_repo(repo)
        with_sei = store.ensure_entity_key(repo_id, "python:function:m.py::f", "lw:eid:has", c0)
        without_sei = store.ensure_entity_key(repo_id, "python:function:m.py::g", None, c0)
        for kid in (with_sei, without_sei):
            store.append_change_event(
                repo_id=repo_id, entity_key_id=kid, commit_sha=c0, path="m.py",
                change_kind="modified", actor="dev", changed_at="2026-06-25T08:00:00+00:00",
            )
    env = commands.reverify_worklist(repo, [with_sei, without_sei], filters={"has_sei": True})
    assert len(env["data"]["items"]) == 1
    summary = env["data"]["verification_summary"]
    total = summary["fresh"] + summary["stale"] + summary["unverified"] + summary["unavailable"]
    assert total == 1  # NOT 2 — proves post-filter computation


def test_unavailable_when_reachability_fails(tmp_path: Path, monkeypatch) -> None:
    repo = _repo(tmp_path)
    c0 = _commit(repo, "m.py", "v0\n")
    # A verification event must exist so covers() is actually consulted.
    commands.verify_record(repo, commit=c0, kind="test_pass", now="2026-06-25T10:00:00+00:00")
    with WarplineStore.open(default_store_path(repo)) as store:
        key_id = _seed_entity_change(store, repo, "python:function:m.py::f", c0)
    # Patch the name in commands' namespace (it imported is_ancestor by name).
    monkeypatch.setattr(commands, "is_ancestor", lambda *a, **k: None)
    env = commands.reverify_worklist(repo, [key_id])
    assert any(i["reason"] == "changed" for i in env["data"]["items"]), (
        "expected at least one 'changed' item"
    )
    item = next(i for i in env["data"]["items"] if i["reason"] == "changed")
    assert item["verification"]["state"] == "unavailable"
    assert item["verification"]["reason"]["reason_class"] == "unreachable"
    assert env["data"]["verification_summary"]["unavailable"] >= 1


def test_stale_sorts_before_fresh_by_default(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    c0 = _commit(repo, "a.py", "v0\n")
    commands.verify_record(repo, commit=c0, kind="test_pass", now="2026-06-25T10:00:00+00:00")
    c1 = _commit(repo, "b.py", "v1\n")
    with WarplineStore.open(default_store_path(repo)) as store:
        repo_id = store.ensure_repo(repo)
        a = store.ensure_entity_key(repo_id, "python:function:a.py::fa", None, c0)
        store.append_change_event(
            repo_id=repo_id, entity_key_id=a, commit_sha=c0, path="a.py",
            change_kind="modified", actor="dev", changed_at="2026-06-25T08:00:00+00:00",
        )
        b = store.ensure_entity_key(repo_id, "python:function:b.py::fb", None, c0)
        for sha in (c0, c1):
            store.append_change_event(
                repo_id=repo_id, entity_key_id=b, commit_sha=sha, path="b.py",
                change_kind="modified", actor="dev", changed_at="2026-06-25T08:00:00+00:00",
            )
    # Seed FRESH first so the natural (pre-presort) order is fresh-then-stale;
    # the presort must flip it. (Catches presort removal: without it the order
    # stays fresh-first and this assertion fails.)
    env = commands.reverify_worklist(repo, [a, b])
    states = [i["verification"]["state"] for i in env["data"]["items"]]
    assert "stale" in states and "fresh" in states
    assert states.index("stale") < states.index("fresh")  # advisory: stale first


def test_fresh_when_verified_at_a_later_commit(tmp_path: Path) -> None:
    # Asymmetric real-git case that catches a covers/is_ancestor argument SWAP:
    # change at c0, verify at c1 (c1 is a DESCENDANT of c0). c0 is an ancestor of
    # c1, so the change IS covered -> fresh. A swapped is_ancestor(verified, change)
    # would compute is_ancestor(c1, c0) -> False and wrongly report not-fresh.
    repo = _repo(tmp_path)
    c0 = _commit(repo, "m.py", "v0\n")
    c1 = _commit(repo, "n.py", "v0\n")  # later commit, descendant of c0
    with WarplineStore.open(default_store_path(repo)) as store:
        key_id = _seed_entity_change(store, repo, "python:function:m.py::f", c0)
    commands.verify_record(repo, commit=c1, kind="test_pass", now="2026-06-25T10:00:00+00:00")
    env = commands.reverify_worklist(repo, [key_id])
    assert any(i["reason"] == "changed" for i in env["data"]["items"]), (
        "expected at least one 'changed' item"
    )
    item = next(i for i in env["data"]["items"] if i["reason"] == "changed")
    assert item["verification"]["state"] == "fresh"
    assert item["verification"]["last_verified_commit"] == c1


def test_unavailable_when_change_commit_no_longer_exists(tmp_path: Path) -> None:
    # Squash/rebase honesty: a change_event whose commit SHA was rewritten away
    # (no longer a real object). With a recorded verification, git reachability
    # cannot be computed -> 'unavailable'/'unreachable', NOT a silent 'unverified'
    # (which would falsely imply "just needs verifying" instead of "trust unknown").
    repo = _repo(tmp_path)
    c0 = _commit(repo, "m.py", "v0\n")
    commands.verify_record(repo, commit=c0, kind="test_pass", now="2026-06-25T10:00:00+00:00")
    ghost = "0" * 40  # a SHA that never existed (rewritten by squash/rebase)
    with WarplineStore.open(default_store_path(repo)) as store:
        repo_id = store.ensure_repo(repo)
        key_id = store.ensure_entity_key(repo_id, "python:function:m.py::f", None, ghost)
        store.append_change_event(
            repo_id=repo_id, entity_key_id=key_id, commit_sha=ghost, path="m.py",
            change_kind="modified", actor="dev", changed_at="2026-06-25T08:00:00+00:00",
        )
    env = commands.reverify_worklist(repo, [key_id])
    assert any(i["reason"] == "changed" for i in env["data"]["items"]), (
        "expected at least one 'changed' item"
    )
    item = next(i for i in env["data"]["items"] if i["reason"] == "changed")
    assert item["verification"]["state"] == "unavailable"
    assert item["verification"]["reason"]["reason_class"] == "unreachable"


def test_stale_first_is_secondary_to_an_explicit_sort(tmp_path: Path) -> None:
    # Proves stale-first is a SECONDARY tiebreak, not a primary override.
    # Uses the same edge-snapshot setup as test_gv_wl_3 (golden_vectors.py:331-351)
    # to produce a depth-1 downstream item.
    #
    # Layout:
    #   X (depth=0, changed, FRESH): changed at c0, verified at c0
    #   Z (depth=0, changed, STALE): changed at c0 and c1 (after verification)
    #   Y (depth=1, downstream, STALE): changed at c0, then at c1 (after verification)
    #
    # With default sort (depth asc), both X and Z (depth=0) must precede Y (depth=1)
    # even though Y is stale and X is fresh. This proves stale-first advisory
    # sort is the SECONDARY key (within ties), not the primary key.
    #
    # Within depth=0, Z (stale) must precede X (fresh) — this is assertion (c).
    #
    # If the presort were placed AFTER apply_sort instead of before, apply_sort
    # would undo the depth ordering and this assertion would fail.
    repo = _repo(tmp_path)
    c0 = _commit(repo, "x.py", "v0\n")
    # Verify at c0 so X is fresh; Z and Y both have a later change (c1) -> stale.
    commands.verify_record(repo, commit=c0, kind="test_pass", now="2026-06-25T10:00:00+00:00")
    c1 = _commit(repo, "y.py", "v1\n")  # later commit; Z and Y change AFTER verification
    head = c1
    with WarplineStore.open(default_store_path(repo)) as store:
        repo_id = store.ensure_repo(repo)
        # X: depth=0, changed entity — fresh (verified at c0, changed only at c0)
        x = store.ensure_entity_key(repo_id, "python:function:x.py::fx", None, c0)
        store.append_change_event(
            repo_id=repo_id, entity_key_id=x, commit_sha=c0, path="x.py",
            change_kind="modified", actor="dev", changed_at="2026-06-25T08:00:00+00:00",
        )
        # Z: depth=0, changed entity — stale (changed at c0 and c1, only c0 covered)
        z = store.ensure_entity_key(repo_id, "python:function:z.py::fz", None, c0)
        for sha in (c0, c1):
            store.append_change_event(
                repo_id=repo_id, entity_key_id=z, commit_sha=sha, path="z.py",
                change_kind="modified", actor="dev", changed_at="2026-06-25T08:00:00+00:00",
            )
        # Y: depth=1, downstream entity — stale (changed at c0 and c1, only c0 covered)
        y = store.ensure_entity_key(repo_id, "python:function:y.py::fy", None, c0)
        for sha in (c0, c1):
            store.append_change_event(
                repo_id=repo_id, entity_key_id=y, commit_sha=sha, path="y.py",
                change_kind="modified", actor="dev", changed_at="2026-06-25T08:00:00+00:00",
            )
        # Mirror test_gv_wl_3: create a FULL edge snapshot with x->y calls edge
        # so blast_radius produces Y as a depth-1 affected item.
        snap = store.create_edge_snapshot(repo_id, head, "loomweave", "test", "FULL")
        store.append_snapshot_edge(
            snap, source_entity_key_id=x, target_entity_key_id=y,
            edge_kind="calls", confidence="resolved",
        )
        x_id = x
    env = commands.reverify_worklist(repo, [x_id, z], depth=2)
    items = env["data"]["items"]
    depths = [it["depth"] for it in items]
    states = [it["verification"]["state"] for it in items]

    # (a) depth stays the PRIMARY ordering — depth 0 before depth 1
    assert depths == sorted(depths), f"depth ordering violated: {depths}"

    # (b) depth-0 fresh item precedes depth-1 stale item
    x_item = next(
        (it for it in items if it["depth"] == 0 and it["verification"]["state"] == "fresh"), None
    )
    y_item = next((it for it in items if it["depth"] == 1), None)
    z_item = next(
        (it for it in items if it["depth"] == 0 and it["verification"]["state"] == "stale"), None
    )
    assert x_item is not None, "expected depth-0 fresh item (X)"
    assert z_item is not None, "expected depth-0 stale item (Z)"
    assert y_item is not None, "expected depth-1 item (Y)"
    assert items.index(x_item) < items.index(y_item), (
        "stale-first presort must NOT override depth primary key"
    )
    assert items.index(z_item) < items.index(y_item), (
        "depth-0 stale item must precede depth-1 item"
    )

    # (c) within depth=0, stale (Z) precedes fresh (X) — same-depth tiebreak
    assert items.index(z_item) < items.index(x_item), (
        "within depth=0, stale item Z must precede fresh item X"
    )

    # Verify the states we observed
    assert x_item["verification"]["state"] == "fresh", f"X should be fresh, got {states}"
    assert z_item["verification"]["state"] == "stale", f"Z should be stale, got {states}"
    assert y_item["verification"]["state"] == "stale", f"Y should be stale, got {states}"
