# Roadmap - Heddle

Updated: 2026-06-13 (PDR-0001)

Sequencing, WSJF / cost-of-delay, and dated forecasts are produced by
program-management. This file records bets as intent, not a delivery schedule.
Do not compute WSJF here; hand the committed bet over for sequencing.

## Now (committed, in-flight)

- **Agent-first MCP readiness recovery** - make MCP the primary Heddle
  experience, not a wrapper over CLI internals, and retire the live-review
  blockers before reopening productization. Metric: Agent impact answer success
  rate. Decision: PDR-0001. Spec: PRD-0001.
- **Federation uplift proof** - keep solo mode useful while adding real
  published-surface enrichment paths that make Heddle better with federation
  members. Metric: 8 of 10 federation dogfood diffs show uplift.

## Next (shaped, decreasing certainty)

- **Bounded live-repo ingestion strategy** - replace unbounded live-member
  backfill with explicit bounded, incremental, and resumable workflows.
- **Post-admission consumer package** - turn Heddle-owned draft contracts into
  owner-approved sibling tickets only after admission.

## Later (directional bets, no order, no dates)

- **Federation conformance oracle inclusion** - add Heddle MCP and JSON fixtures
  to the federation contract corpus after glossary clearance.
- **Richer verification hints** - infer likely test commands from history and
  project metadata without owning work state.
- **Rename and lineage continuity** - improve key-upgrade lineage when
  Loomweave/SEI continuity evidence is available.
