# Roadmap - Heddle

Updated: 2026-06-13 (PDR-0001)

Sequencing, WSJF / cost-of-delay, and dated forecasts are produced by
program-management. This file records bets as intent, not a delivery schedule.
Do not compute WSJF here; hand the committed bet over for sequencing.

## Now (committed, in-flight)

- **Owner-gated federation admission** - product-candidate readiness evidence is
  in place; admission, glossary freeze, and sibling ticket dispatch remain the
  owner's call.
- **Evidence freshness** - keep dogfood, productization, lint/type/test, and
  member-diff gates aligned as Heddle evolves.

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
