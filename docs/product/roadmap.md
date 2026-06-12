# Roadmap - Heddle

Updated: 2026-06-13 (PDR-0001)

Sequencing, WSJF / cost-of-delay, and dated forecasts are produced by
program-management. This file records bets as intent, not a delivery schedule.
Do not compute WSJF here; hand the committed bet over for sequencing.

## Now (committed, in-flight)

- **Agent-first MCP productization** - make MCP the primary Heddle experience,
  not a wrapper over CLI internals. Metric: Agent impact answer success rate.
  Decision: PDR-0001. Spec: PRD-0001.
- **Federation admission readiness** - keep the product candidate useful in
  solo mode while making pairwise integration clean after owner admission.
  Metric: boundary-safe release candidate gate. Decision: PDR-0001.

## Next (shaped, decreasing certainty)

- **MCP usability hardening** - improve tool discovery, schemas, recoverable
  errors, and agent next steps until Heddle is at least as good as existing
  tools in solo mode and better with federation members.
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
