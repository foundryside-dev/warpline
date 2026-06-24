from __future__ import annotations

from typing import Any

from warpline import __version__
from warpline._enrichment import requirements_reason
from warpline.listing import REASON_CLASSES

# FROZEN canonical success envelope (see interface-lock §0). enrichment values
# are a CLOSED vocabulary; ``absent`` (peer present, no fact) is never conflated
# with ``unavailable`` (peer unreachable), and neither is ever a transport error.
ENRICHMENT_VOCAB: dict[str, frozenset[str]] = {
    "sei": frozenset({"present", "absent", "unavailable"}),
    "edges": frozenset({"present", "absent", "stale", "partial", "skipped", "unavailable"}),
    "work": frozenset({"present", "absent", "unavailable"}),
    "risk": frozenset({"present", "absent", "unavailable"}),
    "governance": frozenset({"present", "absent", "unavailable"}),
    "requirements": frozenset({"present", "absent", "unavailable"}),
}

# Default posture: a peer warpline did not consult is reported as the honest
# "unavailable"/"absent" — never an implied clean/allowed/empty state.
_DEFAULT_ENRICHMENT: dict[str, str] = {
    "sei": "absent",
    "edges": "absent",
    "work": "unavailable",
    "risk": "unavailable",
    "governance": "unavailable",
    "requirements": "unavailable",
}


def enrichment_state(**overrides: str) -> dict[str, str]:
    state = dict(_DEFAULT_ENRICHMENT)
    for key, value in overrides.items():
        if key not in ENRICHMENT_VOCAB:
            raise ValueError(f"unknown enrichment key: {key}")
        if value not in ENRICHMENT_VOCAB[key]:
            raise ValueError(f"value {value!r} not in closed vocab for enrichment.{key}")
        state[key] = value
    return state


def local_only_meta(peer_side_effects: list[Any] | None = None) -> dict[str, Any]:
    """The honesty ``meta`` block every warpline-outbound payload carries.

    Single source of truth for the local-only invariant: ``local_only: True`` and
    an explicit (default empty) ``peer_side_effects`` list. ``build_envelope`` uses
    it for the six FROZEN tools; the NON-FROZEN demo/internal CLI verbs
    (``cop`` / ``co-change`` / ``rebuild-coupling``) reuse it so the guarantee
    cannot be silently dropped by a hand-built payload.
    """

    return {
        "producer": {"tool": "warpline", "version": __version__},
        "local_only": True,
        "peer_side_effects": peer_side_effects or [],
    }


def build_envelope(
    schema: str,
    *,
    query: dict[str, Any],
    data: dict[str, Any],
    enrichment: dict[str, str] | None = None,
    enrichment_reasons: dict[str, dict[str, Any]] | None = None,
    next_actions: dict[str, Any] | None = None,
    warnings: list[str] | None = None,
    peer_side_effects: list[Any] | None = None,
) -> dict[str, Any]:
    """Assemble the FROZEN success envelope for a warpline-outbound tool."""

    enrich = enrichment if enrichment is not None else enrichment_state()
    for key, value in enrich.items():
        if key not in ENRICHMENT_VOCAB or value not in ENRICHMENT_VOCAB[key]:
            raise ValueError(f"enrichment.{key}={value!r} violates the closed vocabulary")
    reasons = {"requirements": requirements_reason(), **(enrichment_reasons or {})}
    for dim, carrier in reasons.items():
        if dim not in ENRICHMENT_VOCAB:
            raise ValueError(
                f"enrichment_reasons.{dim} names a dimension outside the closed vocabulary"
            )
        if not isinstance(carrier, dict) or carrier.get("reason_class") not in REASON_CLASSES:
            raise ValueError(
                f"enrichment_reasons.{dim} must be a listing.reason() triple "
                f"(a dict carrying a canonical reason_class)"
            )
    return {
        "schema": schema,
        "ok": True,
        "query": query,
        "data": data,
        "warnings": warnings or [],
        "next_actions": next_actions or {},
        "enrichment": enrich,
        "enrichment_reasons": reasons,
        "meta": local_only_meta(peer_side_effects),
    }
