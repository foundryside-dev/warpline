"""Self-healing SEI re-resolution sweep (Rung 1c).

An entity key minted while loomweave was unavailable keeps ``sei IS NULL``
forever: the ``entity_keys`` UNIQUE index keys on ``COALESCE(sei, '')``, so a
null-sei row and a resolved-sei row for the same locator are distinct
identities and the null row never heals on its own. This sweep is the idempotent
repair: it pages the null-sei worklist, asks loomweave to resolve each locator,
and applies the store's UPDATE-or-merge core (never re-minting a SEI).

Doctrine:
- SEI-orthogonality — the SEI is loomweave's minted identifier, reused verbatim
  via ``resolve_sei_for_locator``; this module never invents or parses one.
- Honesty invariant — the report names the loomweave posture explicitly
  (``present`` / ``absent`` / ``unavailable``). When no client is available the
  sweep is a pure no-op and reports ``unavailable``; it NEVER marks a key
  resolved-to-null.

``sweep_reresolve_sei`` is internal machinery. The ``reresolve-sei`` CLI verb
that drives it is NON-FROZEN/internal — it is not one of the six frozen v1 MCP
tools.
"""

from __future__ import annotations

from pathlib import Path

from warpline.loomweave import ToolClient, resolve_sei_for_locator
from warpline.store import WarplineStore


def sweep_reresolve_sei(
    store: WarplineStore,
    repo: Path,
    client: ToolClient | None,
    limit: int = 200,
) -> dict[str, object]:
    """Re-resolve null-sei entity keys for ``repo``, healing in place.

    Returns ``{scanned, resolved, merged, still_null, loomweave}`` where
    ``loomweave`` is the closed-vocab posture:

    - ``unavailable`` — no client (loomweave absent); a pure no-op, zero rows
      mutated, ``resolved``/``merged`` are 0 and ``still_null == scanned``.
    - ``present`` — a client was available and resolved at least one locator.
    - ``absent`` — a client was available but resolved no locators (the index
      has no SEI for any scanned locator yet).
    """

    repo_id = store.ensure_repo(repo)
    null_keys = store.null_sei_entity_keys(repo, limit=limit)
    scanned = len(null_keys)

    if client is None:
        # Honest no-op: never mark a key resolved-to-null. Every scanned key
        # remains unresolved and the posture is explicitly ``unavailable``.
        return {
            "scanned": scanned,
            "resolved": 0,
            "merged": 0,
            "still_null": scanned,
            "loomweave": "unavailable",
        }

    resolved = 0
    merged = 0
    still_null = 0
    for key in null_keys:
        locator = str(key["locator"])
        key_id = int(str(key["id"]))
        sei = resolve_sei_for_locator(client, locator)
        if sei is None:
            still_null += 1
            continue
        outcome = store.reresolve_entity_key_sei(
            repo_id=repo_id,
            null_key_id=key_id,
            locator=locator,
            resolved_sei=sei,
        )
        action = outcome["action"]
        if action == "resolved":
            resolved += 1
        elif action == "merged":
            merged += 1
        else:  # "noop" — already healed on a prior pass
            still_null += 1

    posture = "present" if (resolved or merged) else "absent"
    return {
        "scanned": scanned,
        "resolved": resolved,
        "merged": merged,
        "still_null": still_null,
        "loomweave": posture,
    }
