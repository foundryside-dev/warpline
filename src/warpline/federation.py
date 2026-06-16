"""include_federation — reverify's cross-member consult (HARD SEAM).

When ``reverify_worklist(... include_federation=True)`` runs, warpline enriches
each affected entity with federation context by CONSULTING other Weft members
through their READ-ONLY surfaces:

  * filigree — issues touching the SEIs (entity-association reverse lookup);
  * wardline — trust/risk findings keyed on the entity qualname (``dossier``);
  * legis   — governance / closure posture for the entity.

THE HONESTY INVARIANT (PDR-0023), applied per-member. include_federation is the
mini-L2 strategic-view: a confident-empty federation block (a member silently
dropped) is the EXACT defect this kills. So every consulted member's sub-result
carries ITS OWN weft-reason:

  * a member that resolved facts          -> reason_class ``clean``;
  * a member reachable but with no fact   -> reason_class ``clean`` (earned empty);
  * a member whose transport raised/timed  -> ``unreachable`` {cause, fix};
  * a member with NO transport wired yet   -> ``disabled``    {cause, fix}
                                              + a transport_blocker for the strike.

A member is NEVER omitted. ``include_federation=False`` produces no federation
block at all (the field is off); ``True`` always produces the block, and the
block always names every member.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Protocol

from warpline.listing import reason
from warpline.loomweave import loomweave_resolve_qualnames
from warpline.siblings import WorkClient, work_enrichment_for_sei

# The members reverify attempts to consult. Order is stable for deterministic
# output. Each appears in the federation block whether or not it had a transport.
FEDERATION_MEMBERS = ("filigree", "wardline", "legis")


# ---------------------------------------------------------------------------
# wardline read transport — `wardline dossier <qualname> <repo>` (findings/risk)
# ---------------------------------------------------------------------------
class RiskClient(Protocol):
    def findings_for_locator(self, locator: str) -> list[dict[str, Any]]:
        """Active trust/risk findings for the entity at ``locator`` ([] = none)."""
        ...


class LegisClient(Protocol):
    def governance_for_sei(self, sei: str) -> list[dict[str, Any]]:
        """Governance/closure posture records keyed on ``sei`` ([] = none)."""
        ...


class WardlineDossierClient:
    """Real wardline read client over the ``wardline dossier`` CLI.

    ``dossier ENTITY PATH`` returns the trust posture for a function qualname,
    including ``trust.active_findings``. This is warpline's READ-ONLY consult of
    wardline's risk surface; it never mutates wardline state.
    """

    def __init__(self, repo: Path, command: str = "wardline", timeout: float = 30.0) -> None:
        self.repo = repo
        self.command = command
        self.timeout = timeout

    def _dossier(self, qualname: str) -> dict[str, Any]:
        proc = subprocess.run(
            [self.command, "dossier", qualname, "."],
            cwd=self.repo,
            check=True,
            text=True,
            capture_output=True,
            timeout=self.timeout,
        )
        payload = json.loads(proc.stdout)
        return payload if isinstance(payload, dict) else {}

    def findings_for_locator(self, locator: str) -> list[dict[str, Any]]:
        # wardline keys on the dotted import qualname, not the warpline locator;
        # reuse the loomweave qualname derivation (src-layout stripped).
        last_error: Exception | None = None
        for qualname in loomweave_resolve_qualnames(locator):
            try:
                payload = self._dossier(qualname)
            except subprocess.CalledProcessError as exc:
                # "entity not found in scanned set" for a bad qualname candidate:
                # try the next candidate before giving up.
                last_error = exc
                continue
            trust = payload.get("trust")
            if not isinstance(trust, dict):
                return []
            active = trust.get("active_findings")
            if isinstance(active, list):
                return [f for f in active if isinstance(f, dict)]
            return []
        if last_error is not None:
            raise last_error
        return []


# ---------------------------------------------------------------------------
# per-member consult — each returns (entries_by_locator, member_reason)
# ---------------------------------------------------------------------------
def _seis(items: list[dict[str, Any]]) -> list[tuple[str, str]]:
    """(locator, sei) pairs for items that carry a non-empty SEI."""

    pairs: list[tuple[str, str]] = []
    for item in items:
        entity = item.get("entity", {})
        sei = entity.get("sei")
        locator = entity.get("locator")
        if isinstance(sei, str) and sei and isinstance(locator, str) and locator:
            pairs.append((locator, sei))
    return pairs


def _consult_filigree(
    items: list[dict[str, Any]], work_client: WorkClient | None
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    if work_client is None:
        return {}, reason(
            "disabled",
            cause="no filigree transport configured for this reverify call",
            fix=(
                "pass a WorkClient (FiligreeWorkClient over filigree's HTTP API, or the "
                "federation client) so reverify can read entity-associations keyed on the SEI"
            ),
        )
    by_locator: dict[str, list[dict[str, Any]]] = {}
    try:
        for locator, sei in _seis(items):
            # Probe the transport DIRECTLY (not through the swallowing
            # work_enrichment_for_sei wrapper) so a genuine transport failure
            # surfaces as ``unreachable`` instead of a confident-empty. The probe
            # raise propagates to the except below; on success we reuse the
            # frozen enrichment shaping for the actual items.
            work_client.associations(sei)
            work = work_enrichment_for_sei(work_client, sei)
            if work:
                by_locator[locator] = work
    except Exception as exc:  # transport raised mid-consult — surface, never drop
        return by_locator, reason(
            "unreachable",
            cause=f"filigree consult raised: {exc!r}",
            fix="confirm the filigree CLI/server is reachable from this repo, then re-run",
        )
    return by_locator, reason("clean")


def _consult_wardline(
    items: list[dict[str, Any]], risk_client: RiskClient | None
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    if risk_client is None:
        return {}, reason(
            "disabled",
            cause="no wardline transport configured for this reverify call",
            fix=(
                "pass a RiskClient (WardlineDossierClient over `wardline dossier`) so reverify "
                "can read active trust findings for each affected entity"
            ),
        )
    by_locator: dict[str, list[dict[str, Any]]] = {}
    try:
        for item in items:
            entity = item.get("entity", {})
            locator = entity.get("locator")
            if not isinstance(locator, str) or not locator:
                continue
            findings = risk_client.findings_for_locator(locator)
            if findings:
                by_locator[locator] = findings
    except Exception as exc:
        return by_locator, reason(
            "unreachable",
            cause=f"wardline consult raised: {exc!r}",
            fix="confirm the wardline CLI is on PATH and the repo is scannable, then re-run",
        )
    return by_locator, reason("clean")


def _consult_legis(
    items: list[dict[str, Any]], legis_client: LegisClient | None
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    if legis_client is None:
        # The legis CLI exposes only serve/mcp/gate verbs — there is NO per-SEI /
        # per-entity governance read on the CLI. Honest posture: disabled with a
        # recruiting fix, NEVER a faked-empty governance result. Reported as a
        # transport_blocker for the strike.
        return {}, reason(
            "disabled",
            cause=(
                "no per-entity legis governance read transport is wired: the legis CLI exposes "
                "serve/mcp/governance-gate only, not a per-SEI closure/posture read"
            ),
            fix=(
                "wire a LegisClient over the legis governance read surface "
                "(GET /api/.../governance keyed on the SEI, or the legis MCP governance read) "
                "and pass it to reverify; until then governance is honestly disabled, not empty"
            ),
        )
    by_locator: dict[str, list[dict[str, Any]]] = {}
    try:
        for locator, sei in _seis(items):
            posture = legis_client.governance_for_sei(sei)
            if posture:
                by_locator[locator] = posture
    except Exception as exc:
        return by_locator, reason(
            "unreachable",
            cause=f"legis consult raised: {exc!r}",
            fix="confirm the legis governance read surface is reachable, then re-run",
        )
    return by_locator, reason("clean")


def consult_federation(
    items: list[dict[str, Any]],
    *,
    work_client: WorkClient | None = None,
    risk_client: RiskClient | None = None,
    legis_client: LegisClient | None = None,
) -> dict[str, Any]:
    """Build the federation block for the reverify worklist ``items``.

    Returns ``{"members": {name: {"weft_reason": ..., "entity_count": int}},
    "entities": [{"locator", "sei", "work"|"risk"|"governance"}]}``. Every member
    in :data:`FEDERATION_MEMBERS` appears in ``members`` carrying its own
    weft-reason; a member with no transport is ``disabled`` (NOT omitted), a
    member that raised is ``unreachable``. The per-entity ``entities`` list only
    carries entries a member actually returned facts for, but the absence of a
    member's facts is always explained by that member's ``weft_reason``.
    """

    work_by, work_reason = _consult_filigree(items, work_client)
    risk_by, risk_reason = _consult_wardline(items, risk_client)
    gov_by, gov_reason = _consult_legis(items, legis_client)

    members = {
        "filigree": {"weft_reason": work_reason, "entity_count": len(work_by)},
        "wardline": {"weft_reason": risk_reason, "entity_count": len(risk_by)},
        "legis": {"weft_reason": gov_reason, "entity_count": len(gov_by)},
    }

    entities: list[dict[str, Any]] = []
    for item in items:
        entity = item.get("entity", {})
        locator = entity.get("locator")
        if not isinstance(locator, str) or not locator:
            continue
        work = work_by.get(locator, [])
        risk = risk_by.get(locator, [])
        gov = gov_by.get(locator, [])
        if not (work or risk or gov):
            continue
        entities.append(
            {
                "locator": locator,
                "sei": entity.get("sei"),
                "work": work,
                "risk": risk,
                "governance": gov,
            }
        )

    return {"members": members, "entities": entities}


def federation_transport_blockers(
    *,
    work_client: WorkClient | None,
    risk_client: RiskClient | None,
    legis_client: LegisClient | None,
) -> list[dict[str, str]]:
    """Members with NO transport wired, as STRIKE_RESULT transport_blockers.

    These mirror the ``disabled`` per-member weft-reasons in the federation block:
    an honest declaration of what cross-member read is still missing, surfaced to
    the strike rather than silently absorbed.
    """

    blockers: list[dict[str, str]] = []
    if work_client is None:
        blockers.append(
            {
                "member": "filigree",
                "need": (
                    "a WorkClient (FiligreeWorkClient over filigree's HTTP API) "
                    "for the reverify call"
                ),
            }
        )
    if risk_client is None:
        blockers.append(
            {
                "member": "wardline",
                "need": (
                    "a RiskClient (WardlineDossierClient over `wardline dossier`) "
                    "for the reverify call"
                ),
            }
        )
    if legis_client is None:
        blockers.append(
            {
                "member": "legis",
                "need": (
                    "a per-entity legis governance read transport — the legis CLI exposes only "
                    "serve/mcp/governance-gate, no per-SEI closure/posture read"
                ),
            }
        )
    return blockers
