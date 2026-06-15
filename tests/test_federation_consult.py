"""include_federation — reverify's hub-blessed cross-member consult.

These pin the HARD SEAM contract:

  1. include_federation=False  -> NO federation block (the field is off).
  2. include_federation=True   -> a federation block whose ``members`` names EVERY
     member, each carrying its OWN weft-reason — a member with no transport is
     ``disabled`` (never silently dropped), a member that returned facts is
     ``clean`` and its facts hang off the per-entity ``entities`` list.
  3. A member whose transport raises mid-consult is ``unreachable`` {cause, fix},
     never a confident-empty.

This is the mini-L2: a confident-empty federation block is the exact defect the
honesty invariant kills, so absence of a member's facts is ALWAYS explained by
that member's weft-reason.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from warpline import commands
from warpline.federation import (
    FEDERATION_MEMBERS,
    consult_federation,
    federation_transport_blockers,
)
from warpline.store import WarplineStore, default_store_path


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, text=True, stdout=subprocess.PIPE
    ).stdout.strip()


def _seed_repo_with_entity(tmp_path: Path, *, sei: str | None) -> tuple[Path, int]:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "agent@example.test")
    _git(repo, "config", "user.name", "Agent")
    (repo / "a.py").write_text("a = 1\n", encoding="utf-8")
    _git(repo, "add", "a.py")
    _git(repo, "commit", "-m", "init")
    head = _git(repo, "rev-parse", "HEAD")
    with WarplineStore.open(default_store_path(repo)) as store:
        repo_id = store.ensure_repo(repo)
        key = store.ensure_entity_key(
            repo_id, locator="python:function:a.py::a", sei=sei, commit_sha=head
        )
    return repo, key


# --------------------------------------------------------------------------- (1)
def test_include_federation_false_omits_block(tmp_path: Path) -> None:
    repo, key = _seed_repo_with_entity(tmp_path, sei="loomweave:eid:x")
    env = commands.reverify_worklist(repo, [key], depth=2)
    assert "federation" not in env["data"]
    assert env["query"]["include_federation"] is False


# --------------------------------------------------------------------------- (2)
def test_include_federation_true_names_every_member_with_a_weft_reason(
    tmp_path: Path,
) -> None:
    repo, key = _seed_repo_with_entity(tmp_path, sei="loomweave:eid:x")
    # No transports passed -> every member must be present and ``disabled``.
    env = commands.reverify_worklist(repo, [key], depth=2, include_federation=True)
    fed = env["data"]["federation"]
    assert set(fed["members"]) == set(FEDERATION_MEMBERS)
    for name, block in fed["members"].items():
        wr = block["weft_reason"]
        assert wr["reason_class"] == "disabled", name
        # non-clean weft-reason MUST carry both cause and fix (the recruiting action)
        assert wr["cause"] and wr["fix"], name
    # ...and each disabled member is surfaced LOUDLY in the warnings stream too.
    assert sum(w.startswith("FEDERATION:") for w in env["warnings"]) == len(FEDERATION_MEMBERS)
    assert env["query"]["include_federation"] is True


def test_a_member_with_a_transport_is_clean_and_carries_facts() -> None:
    """A reachable member that returns facts is ``clean`` and its facts hang off
    the per-entity list — the earned non-empty."""

    items = [{"entity": {"locator": "python:function:a.py::a", "sei": "loomweave:eid:x"}}]

    class FakeWork:
        def associations(self, sei: str) -> list[dict[str, Any]]:
            return [{"issue_id": "weft-1", "entity_kind": "entity_association"}]

        def issue(self, issue_id: str) -> dict[str, Any]:
            return {"status": "open", "priority": 1, "claim_state": "unclaimed"}

    class FakeRisk:
        def findings_for_locator(self, locator: str) -> list[dict[str, Any]]:
            return [{"fingerprint": "f1", "rule": "taint", "severity": "ERROR"}]

    fed = consult_federation(items, work_client=FakeWork(), risk_client=FakeRisk())
    assert fed["members"]["filigree"]["weft_reason"]["reason_class"] == "clean"
    assert fed["members"]["wardline"]["weft_reason"]["reason_class"] == "clean"
    # legis has no transport -> disabled, NOT dropped.
    assert fed["members"]["legis"]["weft_reason"]["reason_class"] == "disabled"
    # the entity carries both members' facts.
    entity = next(e for e in fed["entities"] if e["locator"] == "python:function:a.py::a")
    assert entity["work"] and entity["work"][0]["issue_id"] == "weft-1"
    assert entity["risk"] and entity["risk"][0]["fingerprint"] == "f1"
    assert entity["governance"] == []


# --------------------------------------------------------------------------- (3)
def test_a_raising_transport_is_unreachable_not_empty() -> None:
    items = [{"entity": {"locator": "python:function:a.py::a", "sei": "loomweave:eid:x"}}]

    class Boom:
        def associations(self, sei: str) -> list[dict[str, Any]]:
            raise RuntimeError("filigree CLI exploded")

        def issue(self, issue_id: str) -> dict[str, Any]:
            return {}

    fed = consult_federation(items, work_client=Boom())
    wr = fed["members"]["filigree"]["weft_reason"]
    assert wr["reason_class"] == "unreachable"
    assert "exploded" in wr["cause"] and wr["fix"]


def test_transport_blockers_name_the_missing_members() -> None:
    blockers = federation_transport_blockers(
        work_client=None, risk_client=None, legis_client=None
    )
    members = {b["member"] for b in blockers}
    assert members == set(FEDERATION_MEMBERS)
    # legis blocker names the precise gap (no per-entity CLI read).
    legis = next(b for b in blockers if b["member"] == "legis")
    assert "governance" in legis["need"]
