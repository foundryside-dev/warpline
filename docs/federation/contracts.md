# Heddle Federation Contracts

Status: pre-admission draft, Heddle-owned, blocked by the `not-ready` verdict in
`spike/REPORT.md`.
These fixtures are non-normative until owner admission and glossary clearance.

Heddle exposes read-only, local-first CLI and MCP surfaces over its temporal store.
It owns temporal change facts and dated edge snapshots. It does not own current
structure, requirements, work state, trust policy, or governance.

## MCP tools

- `changed` - changed entities for a rev/range/diff.
- `timeline` - ordered change events for an entity.
- `blast_radius` - downstream affected set over dated snapshots.
- `reverify` - agent-consumable re-verification worklist.

All tools are read-only and local-only. Sibling absence returns explicit
enrichment/completeness fields, not transport failure.
