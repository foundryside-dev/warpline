# Current State - Heddle

Checkpoint: 2026-06-13 - `main` after dogfood readiness gate

## The bet right now

Keep Heddle product-candidate ready while preserving the owner-reserved
federation admission boundary. Heddle must remain at least as good as existing
tools in solo mode and better with federation member enrichment.

## In flight

- Agent-first MCP productization - status: **product-candidate ready**. The
  dogfood evaluator proves 10/10 solo parity through MCP in 2 tool calls or
  fewer.
- Federation admission readiness - status: Heddle-owned contracts and consumer
  ticket package exist as pre-admission drafts; Heddle-side federation uplift is
  implemented and proven in the seeded dogfood lane. Sibling-side tickets remain
  post-admission work.
- Product continuity - status: `docs/product/` created; future sessions should
  RESUME here before reinterpreting the design.

## Current non-admission gaps

- Production ingest/backfill can optionally resolve SEI through Loomweave's
  published `entity_resolve` surface; default hook ingest still avoids the
  dependency.
- Production snapshot capture now has CLI/MCP entrypoints, but `blast_radius` /
  `reverify` must stay covered by dogfood as the surface evolves.
- Federation uplift is Heddle-side ready by implementation plus draft specs;
  sibling-side work remains deferred until owner admission.
- MCP recovery, C-9 runtime placement, and C-13 hostile-input handling are
  covered by tests and must stay release-gated.

## Open questions / blocked-on-owner

- Owner admission: Heddle is not an admitted Weft member until john explicitly
  makes that call.
- Glossary/wire freeze: MCP and JSON shapes remain pre-admission draft until
  glossary clearance and conformance-oracle inclusion.
- Owner decision: whether product-candidate readiness becomes federation
  admission, glossary freeze, and sibling ticket dispatch.

## Last checkpoint did

- Recorded the live-review verdict as `not-ready` in the spike report and
  product docs.
- Hardened initial MCP/runtime defects: malformed JSON degrades instead of
  killing the server, tools advertise output schemas, `changed` feeds
  `reverify` ids, default state moves to `.weft/heddle/`, and undecodable Python
  files degrade to file locators.
- Added `capture-snapshot` / `capture_snapshot` as the production path for
  dated Loomweave edge snapshot capture into local Heddle state.
- Added optional Loomweave-backed SEI resolution for `backfill` and
  `ingest-commit`, with clean degradation when Loomweave is unavailable.
- Added `dogfood-eval`, producing `/tmp/heddle-dogfood-results.json`; current
  run proves 10/10 solo parity and 10/10 federation uplift.

## Next session, start here

Execute [`docs/plans/2026-06-13-heddle-1-0-readiness.md`](../plans/2026-06-13-heddle-1-0-readiness.md).
Keep productization evidence fresh by running `heddle dogfood-eval` before
`heddle productization-gate`. Do not dispatch sibling tickets until owner
admission is explicit.
