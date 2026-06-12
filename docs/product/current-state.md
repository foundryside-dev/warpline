# Current State - Heddle

Checkpoint: 2026-06-13 - `main` after live readiness review

## The bet right now

Retire the live-review blockers that prevent Heddle from being a first-class
agentic MCP product and first-class Weft federation candidate. Heddle must be at
least as good as existing tools in solo mode and better with federation members.

## In flight

- Agent-first MCP productization - status: **not ready**. Live MCP hardening has
  started, but acceptance is blocked until a dogfood evaluator proves 8/10 solo
  parity through MCP in 2 tool calls or fewer.
- Federation admission readiness - status: Heddle-owned contracts and consumer
  ticket package exist as pre-admission drafts; federation uplift is not yet
  implemented through published sibling surfaces.
- Product continuity - status: `docs/product/` created; future sessions should
  RESUME here before reinterpreting the design.

## Current blockers

- Production ingest/backfill does not resolve SEI through Loomweave or another
  published identity surface.
- Production queries do not yet capture or refresh dated edge snapshots, so
  `blast_radius`/`reverify` mostly produce honest `NO_SNAPSHOT` answers.
- Federation uplift is unproven: Loomweave is adapter/test-only and
  Filigree/Wardline/Legis/Charter enrichment paths are not wired.
- MCP is improving but still needs full live-envelope fixtures, recoverable
  argument errors across all paths, bounded outputs, and dogfood proof.
- C-9/C-13 conformance fixes have begun; they need full gate coverage.

## Open questions / blocked-on-owner

- Owner admission: Heddle is not an admitted Weft member until john explicitly
  makes that call.
- Glossary/wire freeze: MCP and JSON shapes remain pre-admission draft until
  glossary clearance and conformance-oracle inclusion.
- Dogfood evidence: the north-star needs a 10-diff solo/federation MCP dogfood
  run before any admission recommendation should be treated as validated.

## Last checkpoint did

- Recorded the live-review verdict as `not-ready` in the spike report and
  product docs.
- Hardened initial MCP/runtime defects: malformed JSON degrades instead of
  killing the server, tools advertise output schemas, `changed` feeds
  `reverify` ids, default state moves to `.weft/heddle/`, and undecodable Python
  files degrade to file locators.

## Next session, start here

Execute [`docs/plans/2026-06-13-heddle-1-0-readiness.md`](../plans/2026-06-13-heddle-1-0-readiness.md).
Do not reopen productization until the executable solo/federation dogfood gate
proves the north-star metric.
