# Changelog

All notable changes to warpline are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and warpline adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

The cross-member MCP seam contracts are versioned independently as
`warpline.<contract>.v1` and frozen at the federation clean-break launch; a `v2`
is a new contract URI, never a mutation of `v1`.

## [Unreleased]

### Added
- **legis governance read consumer (`governance_read.v1`).** `reverify
  --include_federation` now lights up the previously-inert `legis` member with a
  real `LegisGovernanceClient` over the `legis governance-read <SEI>` verb
  (output is always JSON; matched to legis's shipped CLI, no `--json` flag),
  consuming legis's authoritative `governance_read.v1` (verified clearances only:
  operator override / cleared sign-off). Mirrored BYTE-FOR-BYTE as the source of
  truth at `contracts/governance_read.v1.schema.json` (legis OWNS it; warpline
  echoes advisorily and NEVER gates — `GV-LG-1`, no `governance_verdict` in
  output). The mirror tracks legis's hardened discriminated union (`unavailable` ⇒
  non-empty reasons + empty `records`; `checked` ⇒ no `unavailable` key) — a
  backward-compatible tightening, pinned by consumer-side rejection tests so an
  `unavailable` answer can never masquerade as a clean empty.
  The clearance `content_hash` is echoed verbatim, NOT re-derived against the current
  body (governance is an echo, not a warpline-asserted verdict — contrast the
  attest-2 path). Honesty: an empty read is `governance: absent` = "no verified
  clearance," which deliberately conflates *ungoverned*, *unknown-SEI*, and an
  entity **actively BLOCKED awaiting sign-off** — so `absent` is never
  "ungoverned" (disclosed in the schema + the federation reference docs). Wiring
  is **capability-gated**: the client is wired only when the installed legis
  advertises `governance-read`; until then the member is honestly `disabled`
  (capability absent), not a forced `unreachable`, and lights up automatically
  once legis ships the verb. The `governance_read.v1` schema vectors are the
  contract's canonical samples, not a live capture (the read surface is unshipped
  at time of writing).
- **Risk-as-verification: wardline-attest-2 consumer (Rung 2).** Closes the
  `verification_source_absent` gap D1 left open. warpline now consumes a PUSHED,
  UNTRUSTED `wardline-attest-2` evidence bundle and, for a worklist whose impact
  set is genuinely `complete`, reads **proven-good** iff EVERY affected entity is
  attested clean at its CURRENT body — mechanical `(commit, content_hash)`
  equality per SEI against the bundle's boundaries (`verdict == "clean"`, not
  `dirty`, commit pins, content_hash matches loomweave's per-entity body hash).
  The body hash is sourced from the SAME loomweave `entity_resolve` round trip
  warpline already uses for the SEI (`resolve_content_hash_for_locator`); it is
  byte-identical to the value wardline binds into the bundle (verified across
  loomweave's MCP `entity_resolve` and HTTP `/api/v1/identity/sei` surfaces). The
  verdict is an **echo of wardline's authority, signature NOT verified by
  warpline** (`authority: "wardline"`, `signature_verified: false`) — never a
  warpline-minted clean. Every honesty edge (no bundle, non-attest-2 schema,
  dirty tree, null/mismatched commit, `sei_source: "unavailable"`, null sei /
  content_hash, non-clean verdict, ANY unmatched affected entity) degrades to
  `unavailable` with an explicit machine reason; proven-good is all-or-nothing.
  Pure consumer (`_attest.worklist_risk`); layered on D1's completeness gate.
  WIRED on the real surfaces: `warpline reverify --attest-bundle <file>` (CLI) and
  the `attest_bundle` MCP arg ingest the pushed bundle; the verdict is emitted at
  `data.risk_verification` on EVERY worklist (without a bundle it honestly reads
  `verification_source_absent`). The per-SEI current content_hash is fetched from
  the same loomweave `entity_resolve` round trip warpline already makes
  (fail-soft). Documented in `contracts/reverify_worklist.v1.schema.json`.
- **Impact-completeness self-assessment (federation D1).** The reverify worklist
  now carries an additive `data.impact_completeness` object —
  `{status: complete|partial|unknown, as_of, graph_fresh, graph_ref, depth_capped,
  unresolved_count, reasons[]}` — warpline's honest verdict on whether the impact
  set is exhaustive for the change. One object declares BOTH axes: the staleness
  axis (`as_of` producer timestamp + `graph_fresh` + `graph_ref`) and the
  completeness axis (`status` + `depth_capped` + `unresolved_count`).
  `status="complete"` is emitted ONLY when the graph is positively fresh (FULL,
  `commits_behind==0`), the blast traversal hit no depth cap, and zero changed
  entities were unresolved; any gap → `partial`; no graph at all → `unknown`.
  Never `complete` on a guess. A new `depth_capped` signal in the blast traversal
  honestly reports when a depth-bounded scope left reachable impact unexplored.
  This is the field downstream consumers (wardline mirrors it verbatim into
  `producer_completeness`) rely on to NOT treat a narrowed scope as authoritative.
  Published as a drift-checkable contract artifact at
  `contracts/reverify_worklist.v1.schema.json` (JSON Schema, draft 2020-12), which
  validates real worklist output. Consumer side (risk-as-verification): an absent
  or non-`complete` assessment degrades warpline's own risk path to
  `risk=unavailable` with an explicit reason (`completeness_not_declared` /
  `completeness_partial`) — never `clean`. Additive on `.v1`: the FROZEN raw
  snapshot-completeness `data.completeness` STRING enum is unchanged (raw signal
  vs. derived assessment); no `v2` bump.
- **Verification freshness (Rung 2, Track B).** The reverify worklist now carries
  an advisory per-item `verification` block (`fresh` / `stale` / `unverified` /
  `unavailable`) with a trust-decay signal, plus a `verification_summary` rollup —
  answering "what changed since it was last proven good." Sourced from warpline's
  own gate result via a new mutating verb `verify-record` (CLI) /
  `warpline_verification_record` (MCP), the 2nd local-only mutating tool. Advisory
  and enrich-only: it annotates and re-sorts (stale-of-trust first) but NEVER
  filters an item, and NEVER gates. Sibling-sourced verification (wardline/
  filigree/legis) remains honest-absent RESERVED. New schema v4
  (`verification_events`); golden vector `GV-VF-1`. The frozen `warpline.<contract>.v1`
  envelope and the closed 6-key enrichment vocab are untouched (verification rides
  the reverify-item schema, not the enrichment vocab).

### Fixed
- **Weft-reason honesty invariant now survives `python -O`.** `listing.reason()`
  enforced its carrier rule (class-membership, and "every non-clean carrier MUST
  carry both cause and fix") with bare `assert`s, which `-O` strips — so under
  `-O` a hollow `{reason_class: "disabled"}` triple with no cause/fix could ship,
  the exact unexplained-absence the honesty doctrine forbids. Promoted both checks
  to raised `ValueError`, and hardened `build_envelope` to reject a non-clean
  `enrichment_reasons` triple missing cause/fix (closing the parallel
  hand-built-via-kwarg path, which bypassed `reason()` even without `-O`).
  `sei_reason()` is now non-Optional — it raises on an out-of-vocab state, which
  removed four `-O`-strippable narrowing asserts at its call sites. Internal
  hardening only; the frozen `warpline.<contract>.v1` envelope and the closed
  enrichment vocab are unchanged.

## [1.2.0] - 2026-06-24

Minor release: spine hardening. Snapshot capture is now correct-by-construction and
every enrichment dimension carries an explanatory weft-reason. Frozen
`warpline.<contract>.v1` MCP contracts are unchanged; the success envelope gains one
additive top-level key (`enrichment_reasons`).

### Added

- **`enrichment_reasons`** — a new top-level success-envelope key carrying the
  `{reason_class, cause, fix}` weft-reason triple per enrichment dimension, so every
  absence reads as *explained* absence (the closed six-key `enrichment` vocab is
  unchanged). The `sei`, `governance`, and reserved `requirements` dimensions now
  carry triples (never-resolved vs Loomweave-unreachable; rename-feed present vs
  absent; reserved-but-honest), built only from the canonical reason classes.
- **Conformance** — four new golden vectors (`GV-LW-6`, `GV-HON-SEI/GOV/REQ`; 18
  total) lock the atomic-capture and honesty invariants; the golden-vector fixture is
  now portable for the GS-7 5th-producer oracle, with a hub handover package under
  `docs/integration/`.

### Changed

- **Snapshot edge-capture is now correct-by-construction** — a single `BEGIN
  IMMEDIATE` transaction (`capture_snapshot_atomic`) replaces the prior multi-step
  write. A snapshot is never visible until all its edges are committed, and a
  mid-capture failure leaves the prior good snapshot intact (fail-closed, locked by a
  regression test + `GV-LW-6`).

## [1.1.3] - 2026-06-24

Patch release fixing stale self-reported version metadata. Frozen
`warpline.<contract>.v1` MCP contracts remain unchanged.

### Fixed

- `warpline.__version__` is now derived from the installed package metadata
  (`importlib.metadata`) instead of a hand-maintained literal in
  `__init__.py`. That literal went stale at 1.1.2, so `warpline --version`,
  the MCP `serverInfo.version`, and every response envelope's
  `meta.producer.version` reported `1.1.1` on the 1.1.2 build. The version is
  now single-sourced from `pyproject` and cannot drift; the package-version
  test asserts that property rather than pinning a literal.

## [1.1.2] - 2026-06-24

Patch release fixing a post-commit hook hang. Frozen `warpline.<contract>.v1`
MCP contracts remain unchanged.

### Fixed

- The Loomweave MCP client (`LoomweaveMcpClient`) now enforces a single
  per-request **deadline** instead of a per-`select()` timeout. Previously the
  10s timeout was reset on every read, so a `loomweave serve` that emitted any
  output within each window (notifications, log lines, partial frames, or
  unmatched envelopes) while never completing the matching response made
  `call_tool` loop forever — hanging the post-commit hook (the fail-soft
  `try/except` never fired because nothing raised). The read loop now bounds the
  whole request: `select()` is given the *remaining* time and the deadline is
  checked each iteration, so a stalled Loomweave surfaces as a `TimeoutError`
  that the hook's fail-soft path catches.

### Changed

- The installed post-commit hook now wraps each Warpline command in a portable
  `timeout` guard (when `timeout` is on `PATH`) as defense-in-depth, so no
  client can ever wedge a commit workflow.

## [1.1.1] - 2026-06-22

Patch release for snapshot-capture correctness and release hygiene. Frozen
`warpline.<contract>.v1` MCP contracts remain unchanged.

### Changed

- The member-diff release guard is now opt-in, so Warpline-owned gates do not
  fail because sibling repositories have unrelated dirty work.
- Full edge-snapshot capture now reuses one Loomweave stdio MCP session per
  client and batches snapshot-edge writes in a single insert transaction.

### Fixed

- `capture_snapshot` resolves symbolic commit refs like `HEAD` before storing the
  snapshot commit, so later staleness checks compare against a real SHA.
- Snapshot capture no longer publishes `FULL` until edge capture has finished,
  preventing readers from observing a complete snapshot with partial edges.
- `changed_only` snapshot capture now resolves `path`, `qualname`, and `sei`
  scopes to stored entity keys and reports unresolved scoped refs as `DELTA`
  failures instead of a false `FULL`.
- The managed post-commit hook no longer runs synchronous full snapshot capture;
  `warpline doctor --fix` detects and repairs older managed hooks that still do.
- Public docs and evidence no longer expose developer-local absolute paths, and
  `FILIGREE_API_URL` is documented for live Filigree work-state enrichment.

## [1.1.0] - 2026-06-17

Capability-ladder release (Rung 0/1/2). All frozen `warpline.<contract>.v1` MCP
contracts are unchanged — this release is strictly additive.

### Added

- **Temporal co-change graph (schema v3).** Git-history-derived co-change
  coupling between entities, surfaced through the impact/reverify reads (Rung 2
  Track A).
- **Risk/governance enrichment** lit up on the reverify worklist, following the
  closed enrichment vocabulary (`present | absent | unavailable`) (Rung 2 Track C).
- **`include_federation` cross-member consult** re-added and wired as a
  hub-blessed read: reverify consults filigree, wardline, and legis through their
  read-only surfaces, each member carrying its own weft-reason (a member with no
  transport is honestly `disabled`, never silently dropped).
- **Always-on lazy edge-snapshot capture** with git-hook and `doctor` wiring
  (Rung 1d).
- **Self-healing SEI re-resolution sweep** — stale `loomweave:eid:` SEIs are
  re-resolved automatically against live loomweave (Rung 1c).
- **Working-context anchor columns + `detected_context` (schema v2)** (Rung 1b).
- **Temporal COP internals + non-frozen demo CLI**, including a squash-merge
  reconstruction demo (Rung 2 Track D). The demo surface is explicitly non-frozen.
- **Read-surface list-ergonomics microaffordances** (filters/sort/paging) across
  the read tools (G2).

### Changed

- **Ordered migration runner + PRAGMA hardening** — deterministic, gap-safe
  schema migrations (v1→v2→v3) with `user_version` tracking (Rung 1a).
- Internal refactor: extracted `_enrichment` / `_blast` command helpers (Rung 0).
- **Federation contract clarified (no behavior change):** the wardline
  `affected_scope` and legis `preflight_impact` "payloads" are documented as
  consumer-lens names for the single `warpline.impact_radius.v1` wire shape
  `warpline_impact_radius_get` already emits — not separately-emitted schemas
  (matches interface-lock §3A/§4A; pinned by GV-WL-1 / GV-LG-1).

### Fixed

- **filigree work-state seam now consumes filigree's live HTTP surface.** The
  inbound entity-association read previously called a non-existent `filigree`
  CLI verb and never worked against real filigree (only a test fixture proved
  it). It now reads `GET /api/entity-associations?entity_id=<sei>` and
  `GET /api/issue/<id>` (base URL via `FILIGREE_API_URL`, default
  `http://localhost:8724`), degrading honestly to `unreachable` when filigree is
  not running — never a fabricated link or a confident-empty.
- Made impact-radius failure modes **loud** — explicit staleness, miss-set, and
  dead-input signalling instead of a quiet segfault.
- Resolved 10 verified review findings on the capability-ladder branch.

## [1.0.0] - 2026-06-13

First stable release. warpline joins the Weft federation as its 5th member — the
temporal / change-impact authority ("if I touch X, what breaks, and what must I
re-verify?"), implemented to the hub-frozen interface-lock
(`2026-06-13-warpline-interface-lock.md`).

### Added

- **6 frozen outbound MCP tools**, each with an endorsed name and a short shim
  returning identical schema+data:
  - `warpline_change_list` / `changed` — `warpline.change_list.v1`
  - `warpline_entity_timeline_get` / `timeline` — `warpline.entity_timeline.v1`
  - `warpline_entity_churn_count_get` / `churn` — `warpline.entity_churn_count.v1`
    (new: per-entity change-event aggregation; the no-dead-by-design read that
    lights up loomweave's `entity_high_churn_list`)
  - `warpline_impact_radius_get` / `blast_radius` — `warpline.impact_radius.v1`
    (carries the wardline `affected_scope` and legis `preflight_impact` payloads)
  - `warpline_reverify_worklist_get` / `reverify` — `warpline.reverify_worklist.v1`
  - `warpline_edge_snapshot_capture` / `capture_snapshot` — `warpline.edge_snapshot.v1`
    (the only mutating tool; writes `.weft/warpline/` only)
- **Canonical success envelope** (`query`, `data`, `warnings`, `next_actions`,
  `enrichment`, `meta`) with `meta.local_only: true`, `meta.peer_side_effects: []`,
  and a CLOSED `enrichment` vocabulary (`present | absent | unavailable`, plus
  `stale | partial | skipped` for edges). Sibling absence is explicit, never an
  implied clean/allowed state (enrich-only, deconfliction-first).
- **`warpline.error.v1`** with CLOSED `error_code` and `retryability`
  (`retry_safe | retry_with_changes | fatal`) vocabularies.
- **SEI keying**: every entity carries both `locator` and `sei`
  (`loomweave:eid:...`, opaque — warpline never mints or parses it).
- **Federation member lifecycle** (`warpline install` / `warpline doctor`):
  - `install` wires MCP bindings (`.mcp.json` + `~/.codex/config.toml`), the git
    `post-commit` ingest hook, the Claude `SessionStart` hook, the
    `warpline-workflow` skill (into `.claude/skills/` and `.agents/skills/`), the
    CLAUDE.md/AGENTS.md instruction blocks, and `.weft/warpline/` config —
    idempotent, atomic, symlink-safe, and never clobbering a foreign member's
    block.
  - `doctor` verifies every component; `doctor --fix` re-applies anything
    autofixable. JSON via `--json` (`warpline.doctor.v1`).
- **`warpline-workflow` skill** with progressive-disclosure references
  (`contract.md`, `tools.md`, `degrade-and-federation.md`) and a worked example.
- **14 golden vectors** (executable `tests/contracts/test_golden_vectors.py` plus
  a manifest for the GS-7 conformance oracle).

### Fixed

- **HX1 — real SEI resolution.** warpline now sends bare, src-layout-stripped
  dotted qualnames to loomweave `entity_resolve` (which resolves the import path,
  not the filesystem path), keeping prefixed entity ids only for
  `entity_neighborhood_get`. Resolution now returns real `loomweave:eid:` SEIs
  against the live loomweave and is **deployment-independent** (works against
  stock loomweave). Ingest resolves SEIs by default.
- **HX2 — portable executed baseline.** The dogfood baseline uses `git grep`
  instead of a hardcoded `ripgrep` dependency, so it reaches `ready=True` on a
  host without `rg`.

### Notes

- Reserved-shape inbound seams: loomweave is PROVEN and frozen; filigree,
  wardline, and the legis rename feed remain reserved-shape / non-binding until a
  golden vector demonstrates real consumption.

## [0.1.0] - pre-admission

Pre-admission spike: local-first temporal store, git backfill/ingest, the initial
draft MCP surface, and the dogfood readiness gate. Superseded by 1.0.0.
