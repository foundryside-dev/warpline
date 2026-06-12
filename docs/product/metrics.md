# Metrics - Heddle

Last read: 2026-06-13

## North-star

| Metric | Target (falsifiable) | Current | Read on | Trend |
|--------|----------------------|---------|---------|-------|
| Agent impact answer success rate | 8 of 10 dogfood diffs show solo parity with existing tools through MCP in 2 tool calls or fewer; 8 of 10 federation-enriched dogfood diffs show federation uplift over existing tools before admission recommendation | `dogfood-eval` shows 10/10 solo parity and 10/10 federation uplift | 2026-06-13 | passing |

## Input metrics

| Metric | Target | Current | Read on |
|--------|--------|---------|---------|
| MCP primary capability coverage | 4 of 4 core capabilities exposed through `tools/list`: `changed`, `timeline`, `blast_radius`, `reverify` | 4 of 4 | 2026-06-13 |
| Changed-set fast-path latency | p95 <= 250 ms on the planted spike corpus | 48.793924 ms measured in `spike/measurements.json` | 2026-06-13 |
| Reverify honesty coverage | 100% of blast-radius and reverify responses include completeness, staleness, and enrichment state | Production snapshot capture has CLI/MCP entrypoints and dogfood proves enriched reverify output | 2026-06-13 |
| SEI enrichment path | Backfill and ingest can populate opaque SEI when Loomweave resolves an entity; absence degrades explicitly | Optional CLI path implemented and covered by tests | 2026-06-13 |
| Productization evidence gate | Release-candidate gate includes spike harness, dogfood evaluator, productization gate, lint, types, tests, and member-diff guard | Passing when current dogfood output is present; admission still owner-reserved | 2026-06-13 |

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
- Productization is evidence-gated: a `go` report must be paired with dogfood
  results meeting both thresholds before it is allowed.
- Any MCP regression that forces manual database inspection, raw grep, or
  sibling-specific tribal knowledge counts against the north-star.
