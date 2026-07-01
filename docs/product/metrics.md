# Metrics - Warpline

Last read: 2026-06-26 (checkpoint)

## North-star

| Metric | Target (falsifiable) | Current | Read on | Trend |
|--------|----------------------|---------|---------|-------|
| Agent impact answer success rate | At least one real member repo passes an executed baseline (`git diff --name-only` plus `rg`) and Warpline MCP returns a non-empty federation-enriched reverify worklist after real Loomweave snapshot capture | `dogfood-eval` shows 1/1 Lacuna baseline parity, 1/1 real Loomweave uplift, 522 captured edges, and 4 reverify items | 2026-06-13 | passing |

## Input metrics

| Metric | Target | Current | Read on |
|--------|--------|---------|---------|
| MCP primary capability coverage | 4 of 4 core capabilities exposed through `tools/list`: `changed`, `timeline`, `blast_radius`, `reverify` | 4 of 4 | 2026-06-13 |
| MCP survivability smoke | Real stdio MCP conversation completes `initialize`, `tools/list`, a successful tool call, a structured bad-input error, and a second `tools/list` after the error | `warpline mcp-smoke --repo . --json` passes with `ok: true` | 2026-06-13 |
| Tool metadata coverage | 5 of 5 current tools advertise read/local-write status, idempotency, touched local paths, concurrency, repo requirement, and federation dependencies | 5 of 5 | 2026-06-13 |
| Changed-set fast-path latency | p95 <= 250 ms on the planted spike corpus | 48.793924 ms measured in `spike/measurements.json` | 2026-06-13 |
| Reverify honesty coverage | 100% of blast-radius and reverify responses include completeness, staleness, and enrichment state | Production snapshot capture has CLI/MCP entrypoints and real-member dogfood proves enriched reverify output | 2026-06-13 |
| SEI enrichment path | Backfill and ingest can populate opaque SEI when Loomweave resolves an entity; absence degrades explicitly | Optional CLI path implemented and covered by tests | 2026-06-13 |
| Productization evidence gate | Release-candidate gate includes spike harness, dogfood evaluator, productization gate, lint, types, tests, and member-diff guard | Passing when current dogfood output is present; admission still owner-reserved | 2026-06-13 |

## Guardrails

| Metric | Floor / ceiling | Current | Read on |
|--------|-----------------|---------|---------|
| Member repo diff violations | 0 Warpline-caused diffs in Filigree, Wardline, Legis, Loomweave, or Plainweave | 0 beyond recorded baselines | 2026-06-13 |
| Hook commit blocking | 0 nonzero hook exits in normal failure paths | `hook_ingest_exit_code` = 0 | 2026-06-13 |
| Sibling absence crashes | 0 crashes when Loomweave is absent or enrichment is unavailable | Tests cover absent enrichment and `NO_SNAPSHOT`; malformed MCP and undecodable-file fixes added after review | 2026-06-13 |
| Authority-boundary drift | 0 cases where Warpline owns current structure, obligations, work state, trust policy, or governance | Draft contracts and boundary tests pass | 2026-06-13 |

## 2026-06-24 checkpoint readings

No reversal trigger crossed; the hardening bet *strengthened* the scoreboard.

- **North-star** — still passing: `dogfood-eval` reports `ready: True`, real-member
  `parity=1 / uplift=1`, federation uplift 10/10 (2026-06-24). The honesty/staleness
  basis is now correct-by-construction (snapshot capture is atomic and fail-closed;
  a stale snapshot can no longer read as fresh).
- **Reverify honesty coverage** — strengthened: every enrichment dimension now carries
  the `cause + reason_class + fix` triple (PDR-0004), locked by golden vectors
  `GV-HON-SEI/GOV/REQ`. Suite is 18 golden vectors, all green.
- **Hook commit blocking (guardrail)** — a latent breach was found and fixed: the
  Loomweave MCP client had a per-`select` timeout, not a per-request deadline, so a
  stalled `loomweave serve` could hang the post-commit hook indefinitely (defeating
  fail-soft). Fixed + released as **v1.1.2**; hook also gained an OS-level `timeout`
  guard. Tracked `warpline-949bd78421` (closed).
- **Version metadata correctness** — `__version__` was a stale hardcoded literal
  (reported 1.1.1 on the 1.1.2 build, including every envelope's
  `meta.producer.version`); now single-sourced from package metadata. Released
  **v1.1.3**.

## 2026-06-24 readings — v1.2.0 ship + release-grade review

The spine-hardening bet shipped to `main` as **v1.2.0** after a 14-agent
adversarially-verified review (PDR-0006). No reversal trigger crossed.

- **Release-grade review verdict: ship** — 0 confirmed blockers, 0 confirmed majors.
  All frozen-contract invariants independently re-verified (closed six-key vocab,
  `meta.local_only`/`peer_side_effects`, additive `enrichment_reasons`, frozen golden
  vectors); `capture_snapshot_atomic` confirmed correct-by-construction. Integrated
  full suite **338 passed, 1 skipped**; release gate green.
- **Tracked quality debt (4 follow-ups, none blocking)** — warpline-d7d04243b2
  (SKIPPED-path non-atomic, pre-existing), -fc09bdeddd (contract-fixture drift, do
  with the hub handover), -d88e223731 (`reason()` assert→ValueError), -17242c627b
  (atomic ROLLBACK coverage + precondition guard).
- **Install hygiene** — warpline 1.2.0 is the single canonical uv tool; the stale
  pre-rename `heddle` editable venv (which shadowed bare invocations at 1.0.0) was
  retired.

## 2026-06-26 readings — 1.2.0 follow-up burndown

Execution session on the PDR-0006 deferred follow-ups (no bet change; no reversal
trigger crossed).

- **Tracked quality debt** — 3 of the 4 original 1.2.0 review follow-ups now closed:
  warpline-d7d04243b2 (prior session), and this session warpline-fc09bdeddd
  (contract-fixture drift; commit 3f6f652) + warpline-d88e223731 (`reason()`
  assert→ValueError; commit 7683407). Remaining: warpline-17242c627b (atomic ROLLBACK
  coverage + precondition guard). New follow-up filed since: warpline-9eae3eb86a
  (Charter→Plainweave evidence refresh, gated on the plainweave repo).
- **Authority-boundary / honesty guardrail — strengthened.** The weft-reason carrier
  invariant (every non-clean reason carries cause+fix — the "unexplained absence" the
  honesty doctrine forbids) now survives `python -O`: `reason()` and `build_envelope`
  raise `ValueError` instead of relying on `-O`-strippable `assert`s, and `sei_reason`
  is non-Optional. Verified by an independent `python -O` proof plus full suite green
  (5 known env-only `PackageNotFoundError` failures, no 6th); mypy unchanged; ruff clean.
- **Observation filed** — warpline-obs-da4909ac64: the same bare-`assert`-under-`-O`
  pattern remains in `mcp.py`'s inputSchema guard (different module; scoped out of
  d88e223731).
- **No north-star or input-metric change** — no consumer-facing capability shipped this
  session; verification-freshness remains built-but-unreleased on
  `plan/verification-freshness`.

## 2026-06-29 readings — Plainweave requirements consumer (4th federation member)

Acceptance session for the requirements consumer (PDR-0008). No reversal trigger crossed;
the federation seam *strengthened*.

- **Federation member coverage (input) — 3 → 4 live consumers.** The reverify
  `include_federation` seam now has all four members as real consumers: filigree (work),
  wardline (risk), legis (governance), and **plainweave (requirements)** — the dimension
  warpline had never wired. `requirements` no longer rides the reserved
  `disabled`/`unavailable` default when the producer is present.
- **Reverify honesty coverage (input) — held, with the no-silent-clean invariant
  strengthened.** The requirements scalar never collapses `unavailable`→`absent`: a
  reachable producer returning per-entity `unavailable`, or a worklist entity with no SEI
  (identity-unresolved), surfaces envelope `unavailable`, not a confident-empty `absent`.
  Pinned by a discriminating fault-injection test (caught by the adversarial review).
- **Authority-boundary guardrail — held.** No plainweave patch (read-only consult + a
  vendored *copy* of plainweave's golden into warpline fixtures); advisory-never-gates and
  `meta.local_only`/`peer_side_effects:[]` verified on the requirements path.
- **Suite** — full warpline suite 569 passed / 1 skipped / 0 failed; ruff + `mypy src`
  clean. North-star unchanged (no new dogfood-eval run this session).
- **Watch (PDR-0008 reversal trigger):** whether the installed plainweave actually
  advertises `requirements-enrichment` in real member repos — if it never does, the
  dimension reads perpetually `disabled` and adds no signal.

## 2026-06-29 readings — arch-analysis Phase-2 reliability hardening (PDR-0009)

Guardrail-class hardening (U1/U2/U3/U4/U8); no north-star movement (stated honestly),
no reversal trigger crossed.

- **Authority-boundary / data-integrity guardrail — strengthened.** U1 adds a
  `_assert_no_orphans` referential-integrity invariant over the FK-less derived tables
  (`snapshot_edges`, `co_change_pairs`), test/CI-invoked, zero added queries on the
  production merge path — converts a silent-corruption hazard into a loud test failure.
- **Silent-correctness — closed.** U2 replaces the length-only positional guard with a
  per-row **locator identity echo** (independent provenance) that raises `ValueError` on
  equal-length order-drift; adversarially verified to fail-if-reverted. The only
  silent-wrong-answer item in the arch-analysis is now defended.
- **Observability + reliability.** U3 routes the three read-path swallows through
  `health_log` (degradation now traceable, not silent); U4 stamps the throttle marker on
  the capture-RAISE path (no more invisible spin-up re-pay); U8 bounds the loomweave
  client (frame cap + read deadline) so a hung sibling can't wedge a graph read.
- **Suite** — full warpline suite **572 passed / 1 skipped / 0 failed** (one new U2 test
  over the 569 baseline); ruff + `mypy src/warpline` clean; wardline `--fail-on ERROR`
  exit 0. Behavior-preserving; frozen golden vectors intact.

- **⚠️ PDR-0008 watch reading — requirements dimension currently `disabled` in practice.**
  The producer review (this session) found the installed `plainweave` binary is **stale
  (v1.0.0, no `requirements-enrichment` verb)** while source is v1.1.0 with the verb. So
  warpline's capability probe hits the stale binary and the requirements member reads
  `disabled` — the contract is dark end-to-end until a `uv tool install --force` reinstall
  ships v1.1.0 on PATH. This does **not** trip PDR-0008's reversal trigger (which is
  "*never* advertises") — it is a fixable ship gap — but the dimension adds no live signal
  until the reinstall (owner escalation; see `current-state.md`).

## 2026-07-01 readings — v1.3.0 released (PDR-0010)

The accepted stack shipped to `main` as **v1.3.0** (owner-directed). No reversal trigger
crossed by the release.

- **Release gate — green.** Merged `main` passed ruff + `mypy src/warpline` + pytest
  (572 passed / 1 skipped); frozen `warpline.<contract>.v1` data contracts unchanged
  (a clean minor); `git diff release/1.2.0 main` == empty (main holds exactly the release).
- **North-star — now backed by the shipped 4-member stack.** The federation-enriched
  reverify capability (verification-freshness + filigree/wardline/legis/plainweave
  consumers + `project_status`) is live on `main`/`v1.3.0` and installed into the MCP tool
  (`~/.local/bin/warpline` = 1.3.0; the stale heddle-venv shadow retired, so bare
  `warpline` is 1.3.0 too). No new dogfood-eval run this session.
- **✅ Watch RESOLVED (2026-07-01, PDR-0008 / PDR-0010):** the plainweave producer was
  reshipped — the installed binary now advertises **and** serves `requirements-enrichment`,
  and warpline's `PlainweaveRequirementsClient.available()` = **True**, so the `requirements`
  dimension is **wired** (no longer `disabled`). The **four-member federation is fully live**.
  (Reads `unavailable` in warpline's own repo since it isn't a plainweave project — expected;
  present/absent in real plainweave member repos. Minor: `plainweave --version` 1.2.0 vs
  `uv tool list` cache v1.1.0 — verb works regardless.)

## Reading notes

- The north-star is deliberately agent-workflow based. Warpline wins only when an
  agent can use MCP to make a completion/reverify decision at least as well as
  existing tools in solo mode, and better when federation member enrichment is
  available.
- Productization is evidence-gated: a `go` report must be paired with dogfood
  results meeting the real-member parity, real Loomweave uplift, and executed
  baseline thresholds before it is allowed.
- Any MCP regression that forces manual database inspection, raw grep, or
  sibling-specific tribal knowledge counts against the north-star.
- `mcp-smoke` is a survivability and discoverability check, not the full
  contract freeze. Namespaced aliases, specific output schemas, list
  filters/sort, pagination, and resources remain the next P1 MCP work.
