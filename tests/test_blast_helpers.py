"""Characterization tests for the blast-pipeline prep helpers.

Locks ``rev_range_commits`` (bad-range error, None passthrough),
``resolve_changed_inputs`` (known/unknown key ids, sei ref resolution,
rev_range filtering), and ``enrich_blast`` (raw blast dict -> (changed,
affected) shape) BEFORE the Rung 0 extraction moves these bodies into
``warpline._blast``.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import commit, init_repo

from warpline._blast import enrich_blast, resolve_changed_inputs, rev_range_commits
from warpline.errors import BadRevisionError
from warpline.store import WarplineStore


# --------------------------------------------------------------------------- rev_range_commits
def test_rev_range_commits_none_passthrough(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    assert rev_range_commits(repo, None) is None


def test_rev_range_commits_resolves_range(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    first = commit(repo, "a.py", "a = 1\n")
    second = commit(repo, "a.py", "a = 2\n")
    shas = rev_range_commits(repo, f"{first}..{second}")
    assert shas == {second}


def test_rev_range_commits_bad_range_raises(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    commit(repo, "a.py", "a = 1\n")
    with pytest.raises(BadRevisionError):
        rev_range_commits(repo, "no-such-ref..also-bad")


# --------------------------------------------------------------------------- resolve_changed_inputs
def test_resolve_changed_inputs_known_key_id(tmp_path: Path) -> None:
    repo = tmp_path / "store_repo"
    repo.mkdir()
    with WarplineStore.open(tmp_path / "warpline.db") as store:
        repo_id = store.ensure_repo(repo)
        key = store.ensure_entity_key(
            repo_id, locator="python:function:a", sei="sei-a", commit_sha="c1"
        )
        ids, resolved, unresolved = resolve_changed_inputs(
            store,
            repo,
            rev_range=None,
            changed_refs=[],
            changed_entity_key_ids=[key],
        )
    assert ids == [key]
    assert unresolved == []
    assert resolved[0]["entity_key_id"] == key
    assert resolved[0]["sei"] == "sei-a"


def test_resolve_changed_inputs_unknown_key_id_is_a_miss(tmp_path: Path) -> None:
    repo = tmp_path / "store_repo"
    repo.mkdir()
    with WarplineStore.open(tmp_path / "warpline.db") as store:
        store.ensure_repo(repo)
        ids, resolved, unresolved = resolve_changed_inputs(
            store,
            repo,
            rev_range=None,
            changed_refs=[],
            changed_entity_key_ids=[999],
        )
    assert ids == []
    assert resolved == []
    assert unresolved == [
        {
            "ref": {"kind": "warpline_entity_key_id", "value": 999},
            "reason": "unknown_entity_key_id",
        }
    ]


def test_resolve_changed_inputs_sei_ref_resolution(tmp_path: Path) -> None:
    repo = tmp_path / "store_repo"
    repo.mkdir()
    with WarplineStore.open(tmp_path / "warpline.db") as store:
        repo_id = store.ensure_repo(repo)
        key = store.ensure_entity_key(
            repo_id, locator="python:function:a", sei="sei-a", commit_sha="c1"
        )
        ids, resolved, unresolved = resolve_changed_inputs(
            store,
            repo,
            rev_range=None,
            changed_refs=[{"kind": "sei", "value": "sei-a"}],
            changed_entity_key_ids=[],
        )
    assert ids == [key]
    assert resolved[0]["ref"] == {"kind": "sei", "value": "sei-a"}
    assert unresolved == []


def test_resolve_changed_inputs_unresolved_sei_reports_reason(tmp_path: Path) -> None:
    repo = tmp_path / "store_repo"
    repo.mkdir()
    with WarplineStore.open(tmp_path / "warpline.db") as store:
        store.ensure_repo(repo)
        _ids, _resolved, unresolved = resolve_changed_inputs(
            store,
            repo,
            rev_range=None,
            changed_refs=[{"kind": "sei", "value": "missing"}],
            changed_entity_key_ids=[],
        )
    assert unresolved == [
        {"ref": {"kind": "sei", "value": "missing"}, "reason": "sei_not_in_snapshot"}
    ]


def test_resolve_changed_inputs_rev_range_seeds_event_keys(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    first = commit(repo, "a.py", "a = 1\n")
    second = commit(repo, "a.py", "a = 2\n")
    with WarplineStore.open(tmp_path / "warpline.db") as store:
        repo_id = store.ensure_repo(repo)
        key = store.ensure_entity_key(
            repo_id, locator="file:a.py", sei=None, commit_sha=second
        )
        store.append_change_event(
            repo_id=repo_id,
            entity_key_id=key,
            commit_sha=second,
            path="a.py",
            change_kind="modified",
            actor="Agent",
            changed_at="2026-01-01T00:00:00+00:00",
        )
        ids, _resolved, _unresolved = resolve_changed_inputs(
            store,
            repo,
            rev_range=f"{first}..{second}",
            changed_refs=[],
            changed_entity_key_ids=[],
        )
    assert key in ids


# --------------------------------------------------------------------------- enrich_blast
def test_enrich_blast_shapes_changed_and_affected(tmp_path: Path) -> None:
    repo = tmp_path / "store_repo"
    repo.mkdir()
    with WarplineStore.open(tmp_path / "warpline.db") as store:
        repo_id = store.ensure_repo(repo)
        a = store.ensure_entity_key(
            repo_id, locator="python:function:a", sei="sei-a", commit_sha="c1"
        )
        b = store.ensure_entity_key(
            repo_id, locator="python:function:b", sei="sei-b", commit_sha="c1"
        )
        raw = {
            "changed": [{"entity_key_id": a}],
            "affected": [
                {
                    "entity_key_id": b,
                    "depth": 1,
                    "via_edges": [
                        {"from": a, "to": b, "kind": "calls", "confidence": "resolved"}
                    ],
                }
            ],
        }
        changed, affected = enrich_blast(store, repo, raw)
    assert changed == [{"entity": {"locator": "python:function:a", "sei": "sei-a"}}]
    assert affected[0]["depth"] == 1
    assert affected[0]["entity"]["locator"] == "python:function:b"
    via = affected[0]["via_edges"][0]
    assert via == {"from": str(a), "to": str(b), "kind": "calls", "confidence": "resolved"}
