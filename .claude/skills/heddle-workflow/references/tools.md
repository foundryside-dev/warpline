# Heddle tools — exact input/output

Load this when you need a tool's precise arguments or `data` shape. Every tool
returns the frozen success envelope (see `contract.md`); only `data`,
`next_actions`, and the relevant `enrichment` keys are tool-specific. Endorsed
name and short shim are interchangeable and return identical schema+data.

## `heddle_change_list` / `changed` — `heddle.change_list.v1`

Input: `{repo, rev_range?, base_ref?, head_ref?, filters?, sort_by?, sort_order?, limit?, cursor?}`

`data`:
```json
{"items": [{"change_id": "heddle:change:N",
            "entity": {"heddle_entity_key_id": 1, "locator": "...", "sei": null, "path": "..."},
            "change_kind": "modified", "actor": "...", "commit": "...", "changed_at": "..."}],
 "changed_refs": [{"kind": "sei|locator", "value": "..."}],
 "page": {"limit": 50, "next_cursor": null, "has_more": false}}
```
`next_actions` names `heddle_reverify_worklist_get` and `heddle_impact_radius_get`
with ready-to-call arguments. **Call this first.**

## `heddle_entity_timeline_get` / `timeline` — `heddle.entity_timeline.v1`

Input: `{repo, entity_ref|entity, filters?, sort_by?, sort_order?, limit?, cursor?}`

`data.entity` carries `{locator, sei, sei_resolution}` where `sei_resolution` is
`resolved|unresolved|unknown` — heddle's local honesty signal, NOT a lineage claim.

## `heddle_entity_churn_count_get` / `churn` — `heddle.entity_churn_count.v1`

Input: `{repo, entity_refs: [{kind, value}], window?: {since, until, rev_range}, sort_by?, sort_order?, limit?, cursor?}`

`data.items[]`: `{entity: {sei, locator}, churn_count, first_changed_at, last_changed_at, last_actor}`.
A never-observed entity returns `churn_count: 0` (not omitted, not an error).

## `heddle_impact_radius_get` / `blast_radius` — `heddle.impact_radius.v1`

Input: `{repo, rev_range?, changed_refs?, changed_entity_key_ids?, depth?, filters?, sort_by?, sort_order?, limit?, cursor?}`

`data`: `{completeness, staleness: {snapshot_commit, commits_behind},
changed: [{entity}], affected: [{entity, depth, via_edges: [{from, to, kind, confidence}]}], page}`.
`completeness` + `staleness` are MANDATORY in every answer.

## `heddle_reverify_worklist_get` / `reverify` — `heddle.reverify_worklist.v1`

Input: same as impact_radius plus `group_by?`, `include_federation?`.

`data.items[]`: `{entity, priority: P1|P2|P3|unknown, reason: changed|downstream|risk_enriched|requirement_enriched,
depth, why, suggested_verification: [{kind, command}], enrichment: {work, risk, governance, requirements}}`.
Changed entities are always present (reason `changed`); downstream is added when a
snapshot exists. `data.next_actions.filigree[]` holds *candidate* work — heddle
files nothing.

## `heddle_edge_snapshot_capture` / `capture_snapshot` — `heddle.edge_snapshot.v1`

Input: `{repo, commit?, mode?: full|changed_only, changed_refs?, if_stale_after?, max_entities?, dry_run?, idempotency_key?}`.
(No `loomweave_command` — that is server/project config.)

`data`: `{snapshot_id, commit_sha, source, source_version, completeness: FULL|DELTA|SKIPPED,
entities, edges, failed_entities, idempotency: created|already_current|dry_run}`.
The ONLY mutating tool; writes `.weft/heddle/` only.
