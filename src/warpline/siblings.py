from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

# filigree's local dashboard exposes the ADR-029 reads over HTTP; this is its
# default bind. Override with FILIGREE_API_URL when filigree runs elsewhere.
DEFAULT_FILIGREE_API_URL = "http://localhost:8724"

# ---------------------------------------------------------------------------
# filigree work-state seam (SEAM 2 inbound).
#
# warpline reads filigree's ADR-029 entity-association reverse-lookup keyed on the
# SEI to answer "is this changed entity already tracked?". This is ENRICH-ONLY:
# filigree absence yields enrichment.work=unavailable, never a transport error,
# and warpline NEVER files/closes/claims work — proposed work lands in
# next_actions.filigree[] as a candidate a human or write-capable tool executes.
# ---------------------------------------------------------------------------


class WorkClient(Protocol):
    def associations(self, sei: str) -> list[dict[str, Any]]:
        """entity_association_list_by_entity(entity_id=sei) → [{issue_id, ...}]."""
        ...

    def issue(self, issue_id: str) -> dict[str, Any]:
        """issue_get(issue_id) → {id, status, assignee/claim_state, priority}."""
        ...


def _priority_label(value: Any) -> str:
    try:
        rank = int(value)
    except (TypeError, ValueError):
        return "unknown"
    if rank <= 1:
        return "P1"
    if rank == 2:
        return "P2"
    return "P3"


def work_enrichment_for_sei(client: WorkClient, sei: str) -> list[dict[str, Any]]:
    """Frozen enrichment.work[] items for one SEI; [] when nothing is linked."""

    try:
        associations = client.associations(sei)
    except Exception:
        return []
    items: list[dict[str, Any]] = []
    for assoc in associations:
        if not isinstance(assoc, dict):
            continue
        issue_id = assoc.get("issue_id")
        if not isinstance(issue_id, str) or not issue_id:
            continue
        try:
            issue = client.issue(issue_id)
        except Exception:
            issue = {}
        claim_state = issue.get("claim_state") or assoc.get("claim_state")
        if claim_state is None:
            claim_state = "claimed" if issue.get("assignee") else "unclaimed"
        items.append(
            {
                "issue_id": issue_id,
                "issue_status": issue.get("status"),
                "claim_state": claim_state,
                "stale_claim": bool(issue.get("stale_claim", False)),
                "link_kind": assoc.get("entity_kind") or "entity_association",
                "priority": _priority_label(issue.get("priority")),
            }
        )
    return items


def priority_from_work(work_items: list[dict[str, Any]]) -> str:
    order = {"P1": 1, "P2": 2, "P3": 3, "unknown": 9}
    best = "unknown"
    for item in work_items:
        candidate = str(item.get("priority", "unknown"))
        if order.get(candidate, 9) < order.get(best, 9):
            best = candidate
    return best


class FiligreeWorkClient:
    """Real filigree client over filigree's HTTP API (ADR-029 reads).

    The SEI reverse-lookup (``entity_association_list_by_entity``) and
    ``issue_get`` live only on filigree's MCP/HTTP surface — there is NO
    ``filigree`` CLI verb for either — so warpline reads them over HTTP:

      * ``GET /api/entity-associations?entity_id=<sei>`` -> ``{"associations": [...]}``
      * ``GET /api/issue/<issue_id>``                    -> the issue record

    Enrich-only honesty: an HTTP 200 with no bindings returns ``[]``
    (earned-empty), while a genuine transport failure (filigree unreachable,
    timeout, non-2xx) RAISES so ``federation._consult_filigree`` surfaces the
    member as ``unreachable`` rather than a confident-empty. The swallowing
    ``work_enrichment_for_sei`` wrapper degrades to empty enrichment for the
    non-federation reverify path.
    """

    def __init__(
        self, repo: Path, *, base_url: str | None = None, timeout: float = 10.0
    ) -> None:
        self.repo = repo
        resolved = base_url or os.environ.get("FILIGREE_API_URL") or DEFAULT_FILIGREE_API_URL
        self.base_url = resolved.rstrip("/")
        self.timeout = timeout

    def _get(self, path: str, params: dict[str, str] | None = None) -> Any:
        url = f"{self.base_url}{path}"
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(
            url, method="GET", headers={"Accept": "application/json"}
        )
        # urlopen raises URLError/HTTPError on transport failure or non-2xx; we let
        # it propagate so the federation consult can report ``unreachable``.
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            status = getattr(resp, "status", 200)
            if status != 200:
                raise urllib.error.URLError(f"filigree HTTP {status} for {path}")
            body = resp.read().decode("utf-8")
        return json.loads(body)

    def associations(self, sei: str) -> list[dict[str, Any]]:
        payload = self._get("/api/entity-associations", {"entity_id": sei})
        if isinstance(payload, list):
            return [a for a in payload if isinstance(a, dict)]
        if isinstance(payload, dict):
            rows = payload.get("associations") or payload.get("result")
            if isinstance(rows, list):
                return [a for a in rows if isinstance(a, dict)]
        return []

    def issue(self, issue_id: str) -> dict[str, Any]:
        payload = self._get(f"/api/issue/{urllib.parse.quote(issue_id)}")
        if isinstance(payload, dict):
            inner = payload.get("issue")
            return inner if isinstance(inner, dict) else payload
        return {}


# ---------------------------------------------------------------------------
# Rename feed (SEAM 4 inbound, locator-rename shape).
#
# A GENERIC typed locator-rename feed — the same {old_locator, new_locator}
# shape loomweave's GitRename matcher consumes. legis is the named future
# external supplier, but warpline accepts the feed from any supplier and falls
# back to raw git when none is given, so the legis *member* stays non-binding.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RenameFeed:
    renames: list[dict[str, str]] = field(default_factory=list)

    def aliases(self, locator: str) -> list[str]:
        """All locators that are the same entity across recorded renames."""

        forward: dict[str, str] = {}
        for entry in self.renames:
            old = entry.get("old_locator")
            new = entry.get("new_locator")
            if isinstance(old, str) and isinstance(new, str):
                forward[old] = new
        chain = [locator]
        # walk forward through the rename chain
        current = locator
        seen = {locator}
        while current in forward and forward[current] not in seen:
            current = forward[current]
            seen.add(current)
            chain.append(current)
        # walk backward (a new locator's pre-rename names)
        backward = {v: k for k, v in forward.items()}
        current = locator
        while current in backward and backward[current] not in seen:
            current = backward[current]
            seen.add(current)
            chain.append(current)
        return chain
