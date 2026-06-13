# Heddle Federation Contracts

Status: **FROZEN at the clean-break launch cutover** (owner nod 2026-06-13).
Authoritative source: `/home/john/weft/pm/2026-06-13-heddle-interface-lock.md`.
Implement TO this contract; a v2 is a new URI, never a mutation of v1.

Heddle exposes read-only, local-first CLI and MCP surfaces over its temporal
store. It owns temporal change facts and dated edge snapshots. It does not own
current structure, requirements, work state, trust policy, or governance.

## MCP tools (6 frozen, endorsed name + short shim, identical schema+data)

| Endorsed name | Shim | Contract schema |
| --- | --- | --- |
| `heddle_change_list` | `changed` | `heddle.change_list.v1` |
| `heddle_entity_timeline_get` | `timeline` | `heddle.entity_timeline.v1` |
| `heddle_entity_churn_count_get` | `churn` | `heddle.entity_churn_count.v1` |
| `heddle_impact_radius_get` | `blast_radius` | `heddle.impact_radius.v1` |
| `heddle_reverify_worklist_get` | `reverify` | `heddle.reverify_worklist.v1` |
| `heddle_edge_snapshot_capture` | `capture_snapshot` | `heddle.edge_snapshot.v1` |

`heddle_entity_churn_count_get` is the no-dead-by-design read (pure GROUP BY over
`change_events`) that lets loomweave light up `entity_high_churn_list` with no
contract edit. `heddle_impact_radius_get` carries both the wardline
`affected_scope` and legis `preflight_impact` payloads.

## Envelope (frozen)

Every outbound tool returns the canonical success envelope `{schema, ok, query,
data, warnings, next_actions, enrichment, meta}` with `meta.local_only: true`,
`meta.peer_side_effects: []`, and a CLOSED `enrichment` vocabulary
(`present|absent|unavailable`, plus `stale|partial|skipped` for `edges`).
`absent` (peer present, no fact) is never conflated with `unavailable` (peer
unreachable), and neither is ever a transport error. Errors use `heddle.error.v1`
with a CLOSED `error_code` set and `retryability` of
`retry_safe|retry_with_changes|fatal`.

Every entity carries BOTH `locator` and `sei` (`loomweave:eid:...`, opaque —
heddle never mints or parses it). `heddle_entity_key_id` is heddle-internal and
NOT a federation key; siblings key on `sei` (preferred) or `locator`.

All peer-facing behavior is local-only. `heddle_edge_snapshot_capture` mutates
heddle's local `.weft/heddle/` state only; it never mutates sibling repos.
Sibling absence returns explicit enrichment/completeness fields, not transport
failure (enrich-only).

## Inbound seams

- **loomweave** (`entity_resolve`, `entity_neighborhood_get`): PROVEN + FROZEN —
  real consumption (HX1 SEI resolution, edge capture).
- **filigree** (`entity_association_list_by_entity` SEI reverse-lookup +
  `issue_get`): EARNED — heddle consumes it for reverify work enrichment
  (golden vectors GV-FI-1, GV-FI-3). Advisory only; heddle never files/closes/
  claims work.
- **wardline** (finding/risk by SEI): NON-BINDING reserved shape — heddle
  degrades to `risk: unavailable`, never `clean`.
- **legis** (git-rename feed): the generic locator-rename FEED shape is earned
  (GV-LG-2 stitches timeline across renames); legis the member stays a
  non-binding future external supplier. Heddle falls back to raw git.

Golden vectors: `tests/contracts/test_golden_vectors.py` (executable) and
`tests/fixtures/contracts/heddle/golden-vectors.json` (manifest for the GS-7
oracle).
