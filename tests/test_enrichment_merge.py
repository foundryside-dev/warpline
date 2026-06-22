"""Track C — light up the inert risk/governance enrichment in reverify.

The federation consult resolves per-entity risk/governance facts, but the
worklist items carry only the empty ``_empty_enrichment()`` scaffold. Track C
merges the federation facts back onto each item's ``enrichment`` block and lifts
the envelope-level ``risk``/``governance`` scalars off the perpetual default.

These tests pin:

  1. **R6 scalar rule** — ``include_federation=False`` (federation never asked)
     or a member that is disabled/unreachable -> ``unavailable``; a reachable
     member with no findings -> ``absent``; a reachable member with findings ->
     ``present``. ``unavailable`` is NEVER conflated with ``absent``.
  2. **per-item merge** — a reachable wardline finding lands on the matching
     ``item.enrichment.risk`` (no longer the empty scaffold).
  3. **M3 insertion point** — the merge runs over the FULL filtered+sorted list
     BEFORE paging, so a page-2 item is enriched exactly like a page-1 one.

Additive/advisory only (D2): this is the proven-need demonstration, not a
pre-promised contract; it never gates.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from warpline import commands
from warpline.store import WarplineStore, default_store_path


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, text=True, stdout=subprocess.PIPE
    ).stdout.strip()


def _seed_repo_with_entities(
    tmp_path: Path, locators: list[str], *, sei_prefix: str = "loomweave:eid:"
) -> tuple[Path, list[int]]:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "agent@example.test")
    _git(repo, "config", "user.name", "Agent")
    (repo / "a.py").write_text("a = 1\n", encoding="utf-8")
    _git(repo, "add", "a.py")
    _git(repo, "commit", "-m", "init")
    head = _git(repo, "rev-parse", "HEAD")
    keys: list[int] = []
    with WarplineStore.open(default_store_path(repo)) as store:
        repo_id = store.ensure_repo(repo)
        for i, locator in enumerate(locators):
            keys.append(
                store.ensure_entity_key(
                    repo_id, locator=locator, sei=f"{sei_prefix}{i}", commit_sha=head
                )
            )
    return repo, keys


class _FindingsRisk:
    """A reachable wardline RiskClient returning a finding for every locator."""

    def findings_for_locator(self, locator: str) -> list[dict[str, Any]]:
        return [{"fingerprint": f"f-{locator}", "rule": "taint", "severity": "ERROR"}]


class _EmptyRisk:
    """A reachable wardline RiskClient that finds nothing (earned-empty)."""

    def findings_for_locator(self, locator: str) -> list[dict[str, Any]]:
        return []


class _BoomRisk:
    """A wardline RiskClient whose transport raises mid-consult (unreachable)."""

    def findings_for_locator(self, locator: str) -> list[dict[str, Any]]:
        raise RuntimeError("wardline dossier exploded")


class _BoomWork:
    """A filigree WorkClient whose transport raises mid-consult (unreachable)."""

    def associations(self, sei: str) -> list[dict[str, Any]]:
        raise RuntimeError("filigree dashboard exploded")

    def issue(self, issue_id: str) -> dict[str, Any]:
        return {}


def test_findings_populate_item_risk_and_envelope_present(tmp_path: Path) -> None:
    repo, keys = _seed_repo_with_entities(tmp_path, ["python:function:a.py::a"])
    env = commands.reverify_worklist(
        repo, keys, depth=2, include_federation=True, risk_client=_FindingsRisk()
    )
    # envelope-level scalar: wardline reachable + findings -> present.
    assert env["enrichment"]["risk"] == "present"
    # legis has no transport -> unavailable (never absent).
    assert env["enrichment"]["governance"] == "unavailable"
    # the per-item enrichment.risk is no longer the empty scaffold.
    item = next(
        i for i in env["data"]["items"]
        if i["entity"].get("locator") == "python:function:a.py::a"
    )
    assert item["enrichment"]["risk"]
    assert item["enrichment"]["risk"][0]["fingerprint"] == "f-python:function:a.py::a"


def test_include_federation_false_is_unavailable_not_absent(tmp_path: Path) -> None:
    repo, keys = _seed_repo_with_entities(tmp_path, ["python:function:a.py::a"])
    env = commands.reverify_worklist(repo, keys, depth=2)  # include_federation=False
    # never asked -> unavailable, NOT the false-clean "absent".
    assert env["enrichment"]["risk"] == "unavailable"
    assert env["enrichment"]["governance"] == "unavailable"
    # and the per-item enrichment stays the empty scaffold.
    item = env["data"]["items"][0]
    assert item["enrichment"]["risk"] == []
    assert item["enrichment"]["governance"] == []


def test_reachable_but_empty_is_absent(tmp_path: Path) -> None:
    repo, keys = _seed_repo_with_entities(tmp_path, ["python:function:a.py::a"])
    env = commands.reverify_worklist(
        repo, keys, depth=2, include_federation=True, risk_client=_EmptyRisk()
    )
    # reachable wardline, no findings -> earned-empty absent.
    assert env["enrichment"]["risk"] == "absent"


def test_unreachable_member_is_unavailable_not_absent(tmp_path: Path) -> None:
    repo, keys = _seed_repo_with_entities(tmp_path, ["python:function:a.py::a"])
    env = commands.reverify_worklist(
        repo, keys, depth=2, include_federation=True, risk_client=_BoomRisk()
    )
    # a transport that raised is unreachable -> unavailable, never a false absent.
    assert env["enrichment"]["risk"] == "unavailable"


def test_unreachable_filigree_work_is_unavailable_not_absent(tmp_path: Path) -> None:
    repo, keys = _seed_repo_with_entities(tmp_path, ["python:function:a.py::a"])
    env = commands.reverify_worklist(
        repo, keys, depth=2, include_federation=True, work_client=_BoomWork()
    )

    assert env["enrichment"]["work"] == "unavailable"
    assert (
        env["data"]["federation"]["members"]["filigree"]["weft_reason"]["reason_class"]
        == "unreachable"
    )


def test_page_two_item_is_still_enriched(tmp_path: Path) -> None:
    """M3: the merge runs over the FULL filtered+sorted list BEFORE paging, so an
    item that only appears on page 2 is enriched identically to a page-1 item."""

    locators = [
        "python:function:a.py::first",
        "python:function:a.py::second",
    ]
    repo, keys = _seed_repo_with_entities(tmp_path, locators)
    # limit=1 so each changed entity lands on its own page; sort by depth keeps
    # the two changed (depth 0) items in a stable order across the page boundary.
    page1 = commands.reverify_worklist(
        repo,
        keys,
        depth=2,
        include_federation=True,
        risk_client=_FindingsRisk(),
        limit=1,
        sort_by="depth",
        sort_order="asc",
    )
    assert page1["data"]["page"]["has_more"] is True
    cursor = page1["data"]["page"]["next_cursor"]
    page2 = commands.reverify_worklist(
        repo,
        keys,
        depth=2,
        include_federation=True,
        risk_client=_FindingsRisk(),
        limit=1,
        sort_by="depth",
        sort_order="asc",
        cursor=cursor,
    )
    page2_item = page2["data"]["items"][0]
    # the item that surfaced only on page 2 still carries its risk findings.
    assert page2_item["enrichment"]["risk"]
    assert page2_item["enrichment"]["risk"][0]["fingerprint"].startswith("f-")
    # and the page-1/page-2 items are distinct entities (real paging, not a repeat).
    assert (
        page1["data"]["items"][0]["entity"]["locator"]
        != page2_item["entity"]["locator"]
    )
