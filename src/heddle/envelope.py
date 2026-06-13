from __future__ import annotations

from typing import Any

from heddle import __version__

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

# Default posture: a peer heddle did not consult is reported as the honest
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


def build_envelope(
    schema: str,
    *,
    query: dict[str, Any],
    data: dict[str, Any],
    enrichment: dict[str, str] | None = None,
    next_actions: dict[str, Any] | None = None,
    warnings: list[str] | None = None,
    peer_side_effects: list[Any] | None = None,
) -> dict[str, Any]:
    """Assemble the FROZEN success envelope for a heddle-outbound tool."""

    enrich = enrichment if enrichment is not None else enrichment_state()
    for key, value in enrich.items():
        if key not in ENRICHMENT_VOCAB or value not in ENRICHMENT_VOCAB[key]:
            raise ValueError(f"enrichment.{key}={value!r} violates the closed vocabulary")
    return {
        "schema": schema,
        "ok": True,
        "query": query,
        "data": data,
        "warnings": warnings or [],
        "next_actions": next_actions or {},
        "enrichment": enrich,
        "meta": {
            "producer": {"tool": "heddle", "version": __version__},
            "local_only": True,
            "peer_side_effects": peer_side_effects or [],
        },
    }
