"""PDR-0025 cond 1 / E1 — the squash-merge reconstruction demo (Rung 2 Track D).

This is the LOAD-BEARING acceptance fixture for the capability ladder: a
clean-history fixture does NOT satisfy PDR-0025. We build a real squash-merge:

  * N feature-branch commits, each ingested into warpline's store (so their
    change events are on record under the ORIGINAL feature SHAs);
  * ``git merge --squash`` collapses those N commits into ONE new mainline commit
    with a brand-new SHA (the original feature SHAs are NOT mainline ancestors);
  * the feature branch is deleted (its commits become unreferenced).

The demo runs end-to-end through the NON-FROZEN internal ``warpline cop`` CLI
verb (the PUBLIC COP MCP tool is interface-pending) and asserts the bundle
EITHER reconstructs the change set OR honestly degrades with a populated
``weft_reason_class`` — never a confident-empty that reads as "nothing changed".

Two paths are exercised:
  1. A ``sei`` frame keyed on an entity warpline ingested from the feature branch
     STILL reconstructs the timeline (the entity identity survives the squash —
     reconstruction via recorded events, not via the rewritten SHAs).
  2. A ``rev_range`` frame keyed on the NEW squashed mainline SHA finds no
     recorded events (warpline recorded the originals) and degrades to an honest
     ``unresolved_input`` reason class — the bundle is useful (it names why it is
     empty and how to recover), never a false clean.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from conftest import git as _git
from conftest import init_repo as _init_repo

from warpline.git import ingest_commit
from warpline.store import WarplineStore, default_store_path


def _commit_file(repo: Path, name: str, body: str) -> str:
    (repo / name).write_text(body, encoding="utf-8")
    _git(repo, "add", name)
    _git(repo, "commit", "-m", f"feat: {name}")
    return _git(repo, "rev-parse", "HEAD")


def _run_cop(repo: Path, *args: str) -> dict[str, object]:
    proc = subprocess.run(
        [sys.executable, "-m", "warpline.cli", "cop", "--repo", str(repo), "--json", *args],
        check=True,
        text=True,
        capture_output=True,
    )
    payload = json.loads(proc.stdout)
    assert isinstance(payload, dict)
    return payload


def _build_squash_merge_fixture(tmp_path: Path) -> tuple[Path, str, str, str]:
    """Return (repo, feature_locator, squashed_sha, original_feature_tip).

    Mainline gets one base commit; a feature branch gets N commits (each
    ingested); the branch is squash-merged into mainline (new SHA) and deleted.
    """

    repo = _init_repo(tmp_path)
    # Mainline base commit.
    _commit_file(repo, "base.py", "BASE = 0\n")
    main_branch = _git(repo, "rev-parse", "--abbrev-ref", "HEAD")

    # Feature branch: N commits, each ingested under its ORIGINAL feature SHA.
    _git(repo, "checkout", "-b", "feature")
    feature_shas: list[str] = []
    feature_shas.append(_commit_file(repo, "feature.py", "def widget():\n    return 1\n"))
    feature_shas.append(_commit_file(repo, "feature.py", "def widget():\n    return 2\n"))
    feature_shas.append(_commit_file(repo, "feature.py", "def widget():\n    return 3\n"))
    original_feature_tip = feature_shas[-1]

    feature_locator = ""
    with WarplineStore.open(default_store_path(repo)) as store:
        for sha in feature_shas:
            ingest_commit(store, repo, sha)
        events = store.list_change_events(repo)
        for event in events:
            if event.get("path") == "feature.py":
                feature_locator = str(event["locator"])
                break
    assert feature_locator, "feature.py entity should have been ingested"

    # Squash-merge: collapse the N feature commits into ONE new mainline SHA.
    _git(repo, "checkout", main_branch)
    _git(repo, "merge", "--squash", "feature")
    _git(repo, "commit", "-m", "feat: squashed feature")
    squashed_sha = _git(repo, "rev-parse", "HEAD")
    # Delete the feature branch — its original SHAs are now unreferenced.
    _git(repo, "branch", "-D", "feature")

    assert squashed_sha != original_feature_tip
    return repo, feature_locator, squashed_sha, original_feature_tip


def test_squash_merge_sei_frame_still_reconstructs(tmp_path: Path) -> None:
    repo, feature_locator, _squashed, _tip = _build_squash_merge_fixture(tmp_path)
    # The entity identity survives the squash: a sei/locator frame reconstructs
    # the recorded timeline even though the feature SHAs are gone from mainline.
    payload = _run_cop(repo, "--frame", "sei", "--sei", feature_locator)
    assert payload["non_frozen"] is True
    frame = payload["frame"]
    assert isinstance(frame, dict)
    assert frame["weft_reason_class"] == "clean"
    items = payload["items"]
    assert isinstance(items, list)
    assert items, "the squashed feature entity must still reconstruct from recorded events"
    assert all(item["entity"]["path"] == "feature.py" for item in items)


def test_squash_merge_rev_range_on_new_sha_degrades_honestly(tmp_path: Path) -> None:
    repo, _locator, squashed_sha, _tip = _build_squash_merge_fixture(tmp_path)
    # A rev-range keyed on the NEW squashed SHA finds no recorded events (warpline
    # recorded the ORIGINAL feature SHAs). The bundle must degrade HONESTLY — a
    # populated weft_reason_class with cause+fix — never a confident-empty.
    payload = _run_cop(
        repo, "--frame", "rev_range", "--rev-range", f"{squashed_sha}~1..{squashed_sha}"
    )
    items = payload["items"]
    assert isinstance(items, list)
    assert items == [], "the squashed SHA has no recorded warpline events"
    frame = payload["frame"]
    assert isinstance(frame, dict)
    assert frame["weft_reason_class"] == "unresolved_input"
    weft_reason = frame["weft_reason"]
    assert isinstance(weft_reason, dict)
    assert weft_reason["cause"], "honest degradation must name the cause"
    assert weft_reason["fix"], "honest degradation must recruit a fix"


def test_squash_merge_branch_sha_fallback_is_useful(tmp_path: Path) -> None:
    repo, _locator, squashed_sha, _tip = _build_squash_merge_fixture(tmp_path)
    # The branch_sha frame is the ratified squash-merge fallback: branch +
    # episode-boundary via a rev-range, with an honest 'partial' reason class and
    # a fallback warning. The COP must still name every member in coverage.
    payload = _run_cop(
        repo,
        "--frame",
        "branch_sha",
        "--branch",
        "feature",
        "--sha",
        squashed_sha,
    )
    frame = payload["frame"]
    assert isinstance(frame, dict)
    assert frame["weft_reason_class"] == "partial"
    warnings = payload["warnings"]
    assert isinstance(warnings, list)
    assert any("fell back" in str(w) for w in warnings)
    coverage = payload["coverage"]
    assert isinstance(coverage, dict)
    assert coverage["members_total"] == 3
    dark = {d["member"] for d in coverage["dark_sectors"]}
    assert dark == {"filigree", "wardline", "legis"}
