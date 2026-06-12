# Metrics - Heddle

Last read: 2026-06-13

## North-star

| Metric | Target (falsifiable) | Current | Read on | Trend |
|--------|----------------------|---------|---------|-------|
| Agent impact answer success rate | 8 of 10 dogfood diffs show solo parity with existing tools through MCP in 2 tool calls or fewer; 8 of 10 federation-enriched dogfood diffs show federation uplift over existing tools before admission recommendation | Failed live review; dogfood evaluator not yet implemented | 2026-06-13 | blocked |

## Input metrics

| Metric | Target | Current | Read on |
|--------|--------|---------|---------|
| MCP primary capability coverage | 4 of 4 core capabilities exposed through `tools/list`: `changed`, `timeline`, `blast_radius`, `reverify` | 4 of 4 | 2026-06-13 |
| Changed-set fast-path latency | p95 <= 250 ms on the planted spike corpus | 48.793924 ms measured in `spike/measurements.json` | 2026-06-13 |
| Reverify honesty coverage | 100% of blast-radius and reverify responses include completeness, staleness, and enrichment state | Honest `NO_SNAPSHOT` exists, but production snapshot capture is missing | 2026-06-13 |
| Productization evidence gate | Release-candidate gate includes spike harness, productization gate, lint, types, tests, and member-diff guard | Blocked by `Readiness verdict: not-ready` | 2026-06-13 |

## Guardrails

| Metric | Floor / ceiling | Current | Read on |
|--------|-----------------|---------|---------|
| Member repo diff violations | 0 Heddle-caused diffs in Filigree, Wardline, Legis, Loomweave, or Charter | 0 beyond recorded baselines | 2026-06-13 |
| Hook commit blocking | 0 nonzero hook exits in normal failure paths | `hook_ingest_exit_code` = 0 | 2026-06-13 |
| Sibling absence crashes | 0 crashes when Loomweave is absent or enrichment is unavailable | Tests cover absent enrichment and `NO_SNAPSHOT`; malformed MCP and undecodable-file fixes added after review | 2026-06-13 |
| Authority-boundary drift | 0 cases where Heddle owns current structure, obligations, work state, trust policy, or governance | Draft contracts and boundary tests pass | 2026-06-13 |

## Reading notes

- The north-star is deliberately agent-workflow based. Heddle wins only when an
  agent can use MCP to make a completion/reverify decision at least as well as
  existing tools in solo mode, and better when federation member enrichment is
  available.
- The historical bounded spike had a `go` recommendation, but the current
  readiness verdict is `not-ready`; productization must stay blocked until live
  MCP/dogfood evidence proves the minimum bar.
- Any MCP regression that forces manual database inspection, raw grep, or
  sibling-specific tribal knowledge counts against the north-star.
