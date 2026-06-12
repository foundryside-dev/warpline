# Heddle Federation Contracts

Status: productization-ready pre-admission draft, Heddle-owned, backed by the
dogfood readiness gate in `spike/REPORT.md`.
These fixtures are non-normative until owner admission and glossary clearance.

Heddle exposes read-only, local-first CLI and MCP surfaces over its temporal store.
It owns temporal change facts and dated edge snapshots. It does not own current
structure, requirements, work state, trust policy, or governance.

## MCP tools

- `changed` - changed entities for a rev/range/diff.
- `timeline` - ordered change events for an entity.
- `blast_radius` - downstream affected set over dated snapshots.
- `reverify` - agent-consumable re-verification worklist.
- `capture_snapshot` - local dated edge snapshot capture from Loomweave's
  published read surface.

All peer-facing behavior is local-only. `capture_snapshot` mutates Heddle's
local `.weft/heddle/` state only; it never mutates sibling repos. Sibling
absence returns explicit enrichment/completeness fields, not transport failure.
