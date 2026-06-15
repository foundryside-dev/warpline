# Warpline Rung 0/1/2 + Working-Context Capture — Execution Plan

**Status:** execution-ready for the base-impl tracks after the round-2 resolutions below. A second adversarial build-readiness review (reality / doctrine+completeness / sequencing) returned **fix-before-build**; its resolutions are folded in at §Build-readiness review (round 2) and **override the body below where they conflict**. Net effect: **Track B (verification freshness) is deferred** (no wardline resolved-finding surface exists), the COP public surface remains INTERFACE-PENDING, and two cross-member confirmations are newly required (wardline resolved-finding read; filigree `closed_at`).
**Scope:** behaviour-preserving decomposition of `commands.py` (Rung 0), spine stabilization (Rung 1: anchor capture + SEI re-resolution + auto-snapshot), diagnostic + COP read surface (Rung 2).
**Doctrine floor:** enrich-only / never-gating · SEI orthogonality · no-mirror · honesty invariant (present|absent|unavailable) · proven-need · frozen v1 contracts (6 MCP tools + envelope + error vocab; additive only, v2 = new URI never a mutation).

---

## Owner-session review & enhancements (on top of the synthesized plan)

The multi-agent design + 3-dimension review (reality / architecture / doctrine) is sound and the reconciliation log resolves the real blockers. The following are added on review against **PDR-0025** and the repo's shipping discipline — amendments to the plan below, not replacements.

- **E1 — The reconstruction demo is a first-class deliverable, and squash-merge is its acceptance criterion (PDR-0025 cond 1).** The plan builds the *capture* (Rung 1b) and the *reconstruction surface* (Track D `cop.py`) but does not name the **demonstration** itself. Add a deliverable: **`tests/integration/test_reconstruction_demo.py`** that builds a **squash-merge fixture** (N feature-branch commits → one new mainline SHA, feature branch deleted) and asserts the bundle still reconstructs — either via a Legis merge-mapping `{squashed SHAs}→{new SHA}` (if shipped) **or** honestly degrades to `branch + episode-boundary` with an explicit `weft-reason` class. This fixture is the load-bearing pass/fail; a clean-history fixture does **not** satisfy PDR-0025.
- **E2 — Sequencing fence (PDR-0025 cond 3).** The "start NOW" list is correct for *readiness* but must respect priority: the **spine-specific** work (Rung 1b anchor, Track A co-change, Track D COP, the E1 demo) sits **behind** the four-member launch cutover (`weft-4b2f948f70`) and warpline's base-impl fast-follow. The **base-impl stabilization** (Rung 0 refactor, 1a runner, 1c re-resolution, 1d snapshot) is **not** fenced and is the right place to start. Treat the fence as priority, not a hard block.
- **E3 — Per-PR verification gate (repo discipline).** Every track lands behind the full gate, not just "suite green": `uv run ruff check .` · `uv run mypy` (strict) · `uv run pytest -q` · **`wardline scan . --fail-on ERROR`** (Rung 1b/1c/1d/Track A/D all touch git subprocess + loomweave-client input — trust-boundary surface). Fix findings at the boundary.
- **E4 — Dirty-tree honest fallback (PDR-0025 cond 2).** Rung 1b handles detached-HEAD (branch=NULL); add the uncommitted/dirty-tree case: when detection occurs against a dirty work tree, record the anchor with an honest `weft-reason` class (e.g. `working_tree_dirty`) rather than a clean-looking but unstable `head_sha`. Never emit a false-precise anchor.
- **E5 — Co-change ingest kill-switch.** Track A adds derivation to the hot commit/ingest path. Beyond the `>30` fan-out cap and fail-soft `try/except`, add a config/env switch (e.g. `WARPLINE_COCHANGE=0`) to disable derivation entirely, so a pathological repo can opt out without a code change.
- **E6 — Version + changelog.** These are additive **new capabilities**, so when they ship they warrant a **1.1.0** minor bump (settles the earlier open "next version" question for this line of work) with a CHANGELOG entry per track. Track in the eventual release PR, not per-commit.

---

## Build-readiness review (round 2) — applied resolutions

A second adversarial pass (reality / doctrine+completeness / build-sequencing) returned **fix-before-build**. These resolutions are authoritative and **override the body below where they conflict**. Grouped by severity.

### Blockers (must, before build)

- **B1 — `_EDGES_FOR_COMPLETENESS` NameError (Rung 0).** `capture_snapshot` (commands.py:933) reads `_EDGES_FOR_COMPLETENESS`, which stays in `commands.py` while Step 0.3 removes it. Fix: the Step 0.2 rename list is **five** items — add `EDGES_FOR_COMPLETENESS` — and Step 0.3 imports it: `from warpline._enrichment import EDGES_FOR_COMPLETENESS, completeness_warnings, edges_enrichment, is_stale, staleness_warnings`. Update `capture_snapshot`'s reference and add a characterization test covering its dict access.
- **B2 — E1 demo must be end-to-end, and needs a degradation signal.** The COP MCP tool is interface-pending, so the demo can't go through it. Fix: add a **minimal non-frozen internal CLI verb** `warpline cop --repo --frame …` (distinct from the future public MCP tool) so `test_reconstruction_demo.py` exercises a real bundle (satisfies PDR-0025's "useful bundle on rewritten history" reversal clause); and add a `weft_reason_class` field to the COP/frame output so the squash-merge honest-degradation path is assertable. *(Owner: confirm a non-frozen demo CLI is acceptable.)*
- **B3 — backfill anchor semantics (Rung 1b).** Resolve the contradiction: **backfill leaves all three anchor columns NULL** (reconstruction ≠ detection). Drop the "`detected_at` present" claim and assert all-NULL for backfilled rows in `test_anchor_capture.py`. (`INSERT OR IGNORE` means re-backfill won't touch existing rows — acknowledged.)
- **B4 — Track A kill-switch + skip-record missing from steps.** Add an explicit Track A step: read `WARPLINE_COCHANGE` in `update_co_change_pairs` (falsy/zero → skip + return); test `WARPLINE_COCHANGE=0` yields zero `co_change_pairs` rows. Record `coupling_skipped=high_fanout` via `store.log_health` **and** a count in the return dict; test it.
- **B5 — migration version ordering is a HARD gate.** Track A's `co_change_pairs` (v3) **must not merge before** Rung 1b's anchor columns (v2) are on `main` — else a DB opened in the gap lands at `user_version=3` and permanently skips v2. Treat Rung 1b → Track A merge order as a code dependency, not a soft priority.
- **B6 — Track B is DEFERRED (WardlineVerificationClient unbuildable).** Verified against wardline source: `dossier.trust` exposes only `active_findings` (`SuppressionState` ∈ ACTIVE/BASELINED/WAIVED; no RESOLVED, no resolution timestamp; suppressed is a count). There is no verification-event surface, so the fresh/stale/unverified temporal split can't be built. Resolution: **drop Track B from "start now."** The only honest piece available today is a binary *active-findings-present → risk-unverified* signal (no temporal freshness) — and that already overlaps Track C's risk dimension. True verification-freshness moves to **interface-pending**, gated on a new wardline resolved-finding+timestamp read (cross-member confirmation #1).

### Majors (must)

- **M1 — counts.** 5 importers of `warpline.commands` (4 test files + `dogfood.py`), not 4. Rung 0 LOC target is **~780** (assert `< 800`), not ~700; ~700 needs the optional SEAM-8 extraction (Q-pyright).
- **M2 — `_rev_range_commits` sites.** 2 remain in `commands.py` bodies (`change_list`:271, `entity_churn_count`:466); the 3rd (216) moves with `_resolve_changed_inputs` to `_blast.py` and is **not** a separate update site.
- **M3 — Track C insertion point.** Merge fed `risk`/`governance` into items **immediately after `consult_federation` and before `apply_overflow`/`apply_page`** (the full filtered+sorted list). Test a page-2 item is still enriched when `include_federation=True`.
- **M4 — Track D frame-kind specs.** Only `rev_range`/`sei` are specified. Add resolution for `time_window` (add `since`/`until` to `list_change_events`), `edit` (define the git command, e.g. `git diff HEAD`), and `branch_sha` fallback (define the rev-range). Any frame kind with no store support → add the store method or drop it from Track D scope.
- **M5 — reresolve delete target (Rung 1c).** On `IntegrityError` from the repoint UPDATE, **DELETE the null-keyed `change_event` row** (`entity_key_id=null_id`) that conflicts; the resolved-keyed row is canonical. Add a `test_reresolve.py` case where null- and resolved-keyed rows differ on `hunk_summary` and assert the resolved row's data is preserved (data-loss made explicit; Q7).
- **M6 — Rung 1d is always-on internally (pin Option A).** Lazy capture fires internally whenever loomweave is available; **no `auto_capture` inputSchema field is added in this PR** (keeps `test_fastfollow_dead_set_is_empty_for_every_tool` green). The opt-out toggle is interface-pending item 3 only.
- **M7 — co-change call placement (Track A).** Accumulate `entity_key_id`s into a `set[int]` across the full path+locator loop; call `update_co_change_pairs(repo_id, resolved, sorted(ids))` **once per commit after** the loop (and once per sha in backfill) — so the `>30` fan-out cap is per-commit, not per-locator.
- **M8 — E4 dirty-tree: add a context column.** Extend Rung 1b migration v2 with `detected_context TEXT` taking `{NULL/clean, working_tree_dirty, detached_head}` — the honest signal carrier (subsumes the detached-HEAD case and avoids overloading `detected_head_sha=NULL`).
- **M9 — migration reconcile edges + WAL note (Rung 1a).** Handle `user_version==0` with `meta.schema_version != '1'` (warn + adopt the meta value before running v>that). Document that `SCHEMA`'s `PRAGMA journal_mode=WAL` runs via `executescript` implicit-commit for fresh DBs (intentional, outside the `BEGIN IMMEDIATE` migration pattern). CI-test the legacy-reconcile and the `user_version > highest-known` warn paths.
- **M10 — list_change_events/timeline additive-column non-regression.** Add a test that `change_list`/`entity_timeline` return valid output with the new fields present on a v1-then-migrated DB; confirm `append_change_event` names columns explicitly (it does — store.py:233-250).

### Minors / nits (should)

- `test_store.py` has **two** `schema_version()==1` assertions (lines 26 and 35) — update **both** to `==2`.
- `user_version > highest-known` warn path: emit to `health_log`; add a test.
- After Rung 1a, **`SCHEMA` DDL is frozen** — all schema changes go through `MIGRATIONS` (never add columns to `SCHEMA`).
- SQLite ≥3.35 assertion justification is the **`RETURNING` clause** already used in `create_edge_snapshot`, not `DROP COLUMN` (no migration here drops a column).
- Characterization-test helpers: lift `_init_repo`/`_commit` into `tests/conftest.py` rather than importing across test modules.
- **git.py merge coordination:** Rung 1b and Track A both edit `ingest_commit`; land Rung 1b first (the v2<v3 gate already forces this).
- Lazy-capture `LoomweaveProbe` adds ~1–5s to the *first* call against an uncaptured repo, bounded to once per NO_SNAPSHOT DB — acceptable on the fallback path; note it.
- `wardline scan .` (E3) covers all of `src/` incl. new `cop.py`/`verification.py` — no per-module enumeration needed.
- Hook-currency `doctor` check keys on the string `reresolve-sei` in the hook body; test old→fail, new→pass, `--fix`→regenerates.

### Newly-required cross-member confirmations (were not in scope before)

1. **Wardline resolved-finding + timestamp read** — gates real verification-freshness (Track B). None exists today.
2. **Filigree `closed_at`** in issue JSON — gates `FiligreeVerificationClient` (already Q4).

---

## Reconciliation log — what changed from the input designs and why

These are the blocker/major findings from the reality, architecture, and doctrine reviews, resolved into the plan below.

| # | Finding (severity) | Resolution in this plan |
|---|---|---|
| R1 | **Schema-version collision** (BLOCKER, reality+arch): Rung 1 and Rung 2 both claimed `schema_version=2`. | Rung 1 anchor columns → **v2**. Rung 2 `co_change_pairs` → **v3**. Single ordered `MIGRATIONS` list; Rung 2 extends it. `test_store.py` assertion `schema_version()==1` is updated to `==2` in Rung 1, `==3` in Rung 2 (explicit step). |
| R2 | **`_as_int` NameError in `_enrichment.py`** (BLOCKER, arch): plan said `_enrichment.py` imports only `typing.Any`, but `is_stale` calls `_as_int`. | Inline the cast: `_is_stale` reaches `_as_int(behind)` only after the `behind is None` guard, so `int(behind)` is equivalent and removes the dependency. `_enrichment.py` stays import-free. `_as_int` keeps a strict-assert copy in `_blast.py` (for `resolve_changed_inputs`:201) and remains in `commands.py` (for `entity_churn_count`:473). |
| R3 | **`executescript()` breaks `BEGIN IMMEDIATE` atomicity** (BLOCKER, arch): Python's `executescript()` issues an implicit COMMIT. | Migration loop uses `conn.execute(...)` per statement inside explicit `BEGIN IMMEDIATE`/`COMMIT`. `executescript(SCHEMA)` is retained **only** for fresh-DB base-table creation (idempotent via `IF NOT EXISTS`). `PRAGMA user_version=N` is set inside the same transaction (verified settable in-transaction). |
| R4 | **Underscore-prefixed test files silently skipped** (MAJOR, reality+arch): `_test_*.py` is not collected; no `python_files` override in `pyproject.toml`. | Name characterization tests `tests/test_enrichment_helpers.py` and `tests/test_blast_helpers.py` (standard `test_*.py`). No collision with a future file exists today. |
| R5 | **Hook-body change only affects fresh installs** (MAJOR, reality): editing `install.py:hook_body()` does not rewrite already-installed `.git/hooks/post-commit`. | Rung 1 adds an explicit re-install path: `apply_git_hook()` already rewrites the managed block, so the migration note instructs running `warpline install --hooks` / `warpline doctor --fix`. `doctor` surfaces a "hook out of date" check. |
| R6 | **Risk/governance scalar value when `include_federation=False`** (MAJOR, reality): merging fed facts into `item.enrichment` risked emitting `absent` when the peer was never asked. | Explicit rule: federation absent/disabled member → `unavailable`; member reachable, no findings → `absent`; member reachable, findings present → `present`. Mirrors existing `work_state` logic. |
| R7 | **Lazy-capture subprocess inside `blast_radius`** (MAJOR, arch): would put a per-entity ~10s loomweave call into the pure traversal path. | `blast_radius` stays pure — **no `on_missing_snapshot` parameter added**. Lazy capture lives in the tool bodies (`impact_radius`/`reverify_worklist`) only: check `latest_snapshot is None`, attempt scoped capture, then call the unchanged `blast_radius`. |
| R8 | **Co-change O(N²) in hot ingest path** (MAJOR, arch): no per-commit cap; dogfood DB has a 105-entity commit. | Add a per-commit pair cap. Commits with `>30` changed entities skip pair generation and record `coupling_skipped=high_fanout` (low signal-to-noise when everything changes together). All co-change writes are `try/except` fail-soft. |
| R9 | **`compose_temporal_cop` in `federation.py`** (MAJOR, arch): violates that module's reverify-scoped docstring. | New module **`warpline/cop.py`**. `cop.py` imports the three `_consult_*` from `federation.py`; `federation.py` does not import `cop.py` (unidirectional). |
| R10 | **`VerificationClient` premature abstraction** (MAJOR, arch): `FiligreeVerificationClient` needs `closed_at` (not in frozen shape); legis has no transport. | Ship `WardlineVerificationClient` first (resolved-finding = verification event, already available). `FiligreeVerificationClient` deferred behind the `closed_at`-availability confirmation. Legis verification stays honestly `unavailable`. |
| R11 | **SEI-merge survivor ambiguity / UPDATE collision** (MINOR→raised, arch): `UPDATE … OR IGNORE` is not valid; a repoint can hit the `change_events` UNIQUE constraint. | Explicit handler: attempt repoint `UPDATE`; on `IntegrityError` (UNIQUE), `DELETE` the null-keyed duplicate row instead (resolved-keyed row is the survivor). Carry `min(first_seen)`/`max(last_seen)` onto the survivor. Integration test for the twin-collision case is mandatory. |
| D1 | **Commit-keyed temporal axis vs ratified work-session episode** (MAJOR, doctrine): proposal ratifies a work-session episode boundary with squash/rebase fallback. | Per-event anchor columns (v2) are kept as the **substrate**, but the design explicitly records `detected_head_sha` as the working-context key distinct from `commit_sha`, and documents the **v4 `change_episodes` superset** as the work-session collapse target. Episode-boundary semantics are an OPEN QUESTION to confirm before any episode table is built — not built in this plan. Co-change (Rung 2) is keyed on commit for now and flagged as needing episode-collapse re-keying once the boundary is ratified (OPEN QUESTION Q6). |
| D2 | **Rung 2 overclaims risk/governance as "promised-frozen"** (MAJOR, doctrine): wardline/legis inbound are RESERVED-SHAPE pending proven-need. | Reworded: the enrichment merge pass is the **proven-need demonstration that earns the freeze**, not a pre-promised contract. It is additive and reversible; it does not lock the wardline/legis inbound shape. |
| r-minor | Misc reality nits: `_as_int` not called in `_rev_range_from_refs`; "30 test files" → 4 files import `commands` (31 total test files); `install_support.py:307-319` is `check_git_hook` not the body; `loomweave timeout=10` is per-tool-call. | Corrected inline throughout. |

---

## Sequencing & dependency graph

```
Rung 0 (refactor, no schema)         ── unblocks clean module boundaries for everything
   │
   ├─► Rung 1a  Migration runner (store.py)        ── PREREQUISITE GATE for all schema work
   │      ├─► Rung 1b  Anchor columns (v2) + git.py population
   │      ├─► Rung 1c  SEI re-resolution sweep (reresolve.py + store merge core + CLI)
   │      └─► Rung 1d  Auto/lazy snapshot capture (tool bodies + hook + doctor)
   │
   └─► Rung 2 (each track independent PR):
          Track C  Enrichment merge pass (reverify) ── SMALL, ship FIRST (tracer bullet)
          Track A  Co-change graph (v3)             ── depends on Rung 1a runner
          Track B  Verification freshness (wardline-only first)
          Track D  COP internals (cop.py)           ── public surface INTERFACE-PENDING
```

Hard dependencies: Rung 1b/c/d and Rung 2 Track A all depend on **Rung 1a (migration runner)**. Track C depends only on Rung 0. Tracks B and D depend only on Rung 0. The COP public tool and the anchor-output-on-frozen-tools surface depend on the user's concrete interface (see §INTERFACE PENDING).

---

## RUNG 0 — Behaviour-preserving decomposition of `commands.py`

**Goal:** drop `commands.py` from 959 LOC by extracting two internal helper modules. Zero change to `cli.py`, `mcp.py`, the 6 `SCHEMA_*` constants, and the 7 tool signatures.

### Module layout (3 modules total)

```
src/warpline/
  commands.py        # ~700 LOC: 7 tool bodies + 6 SCHEMA_* + local helpers
  _enrichment.py     # NEW ~85 LOC: pure staleness/completeness helpers
  _blast.py          # NEW ~130 LOC: blast-pipeline prep helpers
```

Underscore-prefixed module names signal internal-API status; no `__init__.py` re-export. Dependency is strictly one-way: `commands.py → {_enrichment, _blast}`; neither imports `commands`.

> Naming note (arch minor): the reviewer suggested `_staleness.py`/`_resolver.py` as more cohesive. Acceptable either way; this plan keeps `_enrichment`/`_blast` for continuity with the doctrine vocabulary ("enrichment") and the `blast_radius` consumer. Decide at implementation; it is a rename, not a structural change.

### Step 0.1 — Characterization tests (prerequisite, locks behaviour before any move)

- **New:** `tests/test_enrichment_helpers.py` — unit tests for `is_stale` (commits_behind=0/>0/None+snapshot/None+no-snapshot), `edges_enrichment` (each completeness × stale/fresh), `staleness_warnings` (known/unknown commits_behind), `completeness_warnings` (NO_SNAPSHOT/SKIPPED/DELTA/FULL). Pure functions, no fixtures. Import from `commands` initially.
- **New:** `tests/test_blast_helpers.py` — tests for `rev_range_commits` (BadRevisionError on bad range, None passthrough), `resolve_changed_inputs` (known/unknown key ids, sei ref resolution, rev_range filtering — reuse `_init_repo`/`_commit` fixture pattern from `test_honesty_invariant.py`), `enrich_blast` (raw dict → (changed, affected) shape). Import from `commands` initially.
- Run full suite (166 tests + new) green. Baseline.
- **Doctrine:** these are the safety net proving extraction is behaviour-preserving; no contract touched.

### Step 0.2 — Create `_enrichment.py`

- Move `_is_stale`, `_edges_enrichment`, `_staleness_warnings`, `_completeness_warnings`, and the `_EDGES_FOR_COMPLETENESS` constant. Rename public (drop leading underscore): `is_stale`, `edges_enrichment`, `staleness_warnings`, `completeness_warnings`.
- **R2 fix:** in `is_stale`, replace `return _as_int(behind) > 0` with `return int(behind) > 0` (reached only after `behind is None` guard). Module imports: `from __future__ import annotations`, `from typing import Any`. **No `_as_int`, no store, no git, no I/O.**
- Retarget `tests/test_enrichment_helpers.py` imports to `warpline._enrichment`. Suite green. Commit.
- **Doctrine (enrich-only):** `_enrichment.py` is structurally incapable of gating — verified by its import list (only `typing.Any`).

### Step 0.3 — Wire `_enrichment.py` into `commands.py`

- Add `from warpline._enrichment import completeness_warnings, edges_enrichment, is_stale, staleness_warnings`. Update 8 call sites. Remove the 4 bodies + constant from `commands.py`. Suite green. Commit.

### Step 0.4 — Create `_blast.py`

- Move `_rev_range_commits` → `rev_range_commits`, `_resolve_changed_inputs` → `resolve_changed_inputs`, `_enrich_blast` → `enrich_blast`. Keep a **private strict-assert `_as_int`** copy in `_blast.py` (for `resolve_changed_inputs`).
- **R2 note in code:** add a one-line comment that `_blast._as_int` is the strict-`assert isinstance(value, int)` form (matching the original `commands._as_int`), deliberately distinct from `propagation._as_int` (permissive int|str). Do not import either across modules.
- Imports: `from __future__ import annotations`, `subprocess`, `pathlib.Path`, `typing.Any`, `warpline.errors.BadRevisionError`, `warpline.store.WarplineStore`, `warpline.refs.entity_view`. `WarplineStore` is a **parameter**, never opened inside.
- Retarget `tests/test_blast_helpers.py` to `warpline._blast`. Suite green.
- **Doctrine (no-mirror / SEI-orthogonality):** `_blast.py` reads the store passed in, calls git rev-list, writes nothing, mints no identifier; operates on warpline-local `entity_key_id` integers and SEI strings supplied by the store.

### Step 0.5 — Wire `_blast.py` into `commands.py`

- Add `from warpline._blast import enrich_blast, resolve_changed_inputs, rev_range_commits`. Update call sites: `_rev_range_commits` → `rev_range_commits` (2: `change_list`, `entity_churn_count`); `_resolve_changed_inputs` → `resolve_changed_inputs` (2: `impact_radius`, `reverify_worklist`); `_enrich_blast` → `enrich_blast` (2). `commands._as_int` **stays** (still used by `entity_churn_count`:473). Remove the 3 moved bodies. Suite green. Commit.

### Step 0.6 — Verify

- `wc -l src/warpline/commands.py` (~700 target); `python -c 'import warpline.commands, warpline._enrichment, warpline._blast'` clean; full suite green; run pyright on the module.
- **Open watch (Q-pyright):** if pyright still times out at ~700 LOC, the deferred SEAM-8 `_process_blast_result()` extraction becomes a Rung 0.5; track the pyright output and decide then. Not done now (the post-step divergence between `impact_radius` and `reverify_worklist` makes a unified helper a parameter-explosion until Rung 1 lands).

**What stays in `commands.py`:** all 7 tool bodies (unchanged signatures), all 6 `SCHEMA_*`, `session_context`, `_rev_range_from_refs`, `_coerce_max_entities`, `_coerce_if_stale_after`, `_federation_warnings`, `_page`, `_filters_echo`, `_unresolved_warnings`, `_as_int`.

**Caller impact:** 4 files import `warpline.commands` (3 test files + `dogfood.py`); none import private helpers. Zero import-path changes. `mcp.py` `TOOL_SPECS` references `commands.SCHEMA_*` — unaffected.

---

## RUNG 1 — Stabilize the spine

### Rung 1a — Migration runner (PREREQUISITE GATE)

`store.py:open()` currently runs `executescript(SCHEMA)` unconditionally and never consults `schema_version()`. Add a real ordered runner.

**Changes — `store.py`:**
- Connection setup: keep `journal_mode=WAL`; add `PRAGMA foreign_keys=ON; PRAGMA busy_timeout=5000; PRAGMA synchronous=NORMAL`. Assert `sqlite3.sqlite_version_info >= (3,35,0)` (ALTER … DROP COLUMN floor; CI must verify the deployment Python's bundled SQLite — OPEN QUESTION Q-sqlite).
- Keep `executescript(SCHEMA)` for fresh-DB base tables (idempotent `IF NOT EXISTS`).
- **R3:** introduce `MIGRATIONS: list[Migration]`, each `(version:int, apply:Callable[[Connection],None])`. Runner:
  1. Read `PRAGMA user_version`. Legacy reconcile: if `user_version==0` and `meta.schema_version=='1'`, set `user_version=1` once.
  2. For each step with `version > user_version`: `conn.execute("BEGIN IMMEDIATE")`; run the step's `conn.execute(...)` statements (**never `executescript`**); `conn.execute(f"PRAGMA user_version = {N}")`; `UPDATE meta SET value=? WHERE key='schema_version'` to `N`; `conn.execute("COMMIT")`.
  3. Concurrent `open()`: second writer blocks on RESERVED lock, re-reads `user_version`, skips applied steps (idempotent).
- Add guard: if on-disk `user_version` > highest known, **warn (do not fail)** — reads remain safe (additive-only history).

**Tests — `tests/test_store_migrations.py` (NEW):** fresh-DB lands at highest version; legacy-v1 DB (only base tables + `meta.schema_version='1'`) upgrades on open; idempotent re-open is a no-op; two concurrent `open()` calls do not double-apply (thread/`busy_timeout` test). **Update** existing `test_store.py` `schema_version()` assertion `1 → 2`.

**Doctrine (no-mirror / honesty):** runner only manages warpline's own store under `.weft/warpline/`; additive columns read NULL = `unavailable`, never a clean default.

### Rung 1b — Working-context anchor columns (schema v2)

The anchor identifies a **change episode** (verb-moment), orthogonal to SEI (entity, noun) — so it lives on `change_events`, **not** `entity_keys`.

**Migration 2 DDL** (all NULLable, no default, O(1) metadata-only):
```
ALTER TABLE change_events ADD COLUMN detected_branch    TEXT;  -- git symbolic-ref short name; NULL if detached
ALTER TABLE change_events ADD COLUMN detected_head_sha  TEXT;  -- HEAD sha AT DETECTION (working context; distinct from commit_sha = introducing commit)
ALTER TABLE change_events ADD COLUMN detected_at        TEXT;  -- ISO-8601 UTC detection timestamp (distinct from changed_at = author time)
```

**Changes:**
- `store.py:append_change_event` — add optional kwargs `detected_branch/detected_head_sha/detected_at` (NULL when unsupplied → backward compatible). Add the 3 columns to `list_change_events` and `timeline` SELECT lists so reads can surface the anchor (existing callers ignore extra keys).
- `git.py:ingest_commit` and `backfill` — compute the anchor **once per call**: `head_sha = git rev-parse HEAD`; `branch = git symbolic-ref --short -q HEAD` (None on detached); `detected_at = datetime.now(UTC).isoformat()`. Thread into `append_change_event`. **`backfill` sets branch/head = NULL** (reconstruction, not detection), `detected_at = now` as a reconstruction marker → historical rows read `unavailable` working-context (honest).

**D1 note:** per-event columns are the **substrate**; the work-session episode boundary (ratified in the proposal with squash/rebase fallback) is recorded as the target of a future **`change_episodes` table (v4)** that the per-event triple collapses into cleanly. No episode table built here. Confirm episode semantics (Q5) before building it.

**Tests — `tests/test_anchor_capture.py` (NEW):** ingest on a branch records branch + head_sha + detected_at; detached HEAD records branch=NULL; backfill records branch/head=NULL + detected_at present; `list_change_events`/`timeline` surface the new fields; v1-DB-opened-by-v2-client migrates and old rows read NULL.

**Doctrine (SEI-orthogonality):** no new identifier minted — branch/head are git's values, `detected_at` is a clock reading; warpline owns only the contract of recording them. Anchor on `change_events` (the detection act), never on `entity_keys`.

### Rung 1c — Self-healing SEI re-resolution sweep

The bug is the `UNIQUE(repo_id, locator, COALESCE(sei,''))` index (store.py:30-31): a `sei=NULL` row and a resolved-sei row for the same locator are distinct identities, so a row minted while loomweave was down stays null forever. Fix = idempotent **UPDATE-or-merge** (never re-mint).

**Changes:**
- `store.py` — new `null_sei_entity_keys(repo, limit) -> list[{id, locator}]`: select `WHERE sei IS NULL`, bounded, ordered by id (deterministic, resumable).
- `store.py` — new `reresolve_entity_key_sei(repo_id, null_key_id, locator, resolved_sei) -> {action}`. **R11 explicit merge:** inside `BEGIN IMMEDIATE`:
  1. `UPDATE entity_keys SET sei=? WHERE id=? AND sei IS NULL`.
  2. On `sqlite3.IntegrityError` (twin exists): repoint `UPDATE change_events SET entity_key_id=:twin WHERE entity_key_id=:null_id`; for each row that hits the `change_events` UNIQUE constraint, catch and **`DELETE` the null-keyed duplicate** (resolved-keyed row is the survivor); then `DELETE` the orphan null `entity_keys` row.
  3. Carry `first_seen = min`, `last_seen = max` onto the survivor.
  - Convergent: re-running on a healed key matches no null rows → no-op.
- `reresolve.py` (NEW) — `sweep_reresolve_sei(store, repo, client, limit) -> {scanned, resolved, merged, still_null, loomweave: present|absent|unavailable}`. Pages null keys, calls `loomweave.resolve_sei_for_locator` per locator, applies the merge core. **No-op + honest report when `client is None`** (never marks a key resolved-to-null).
- `cli.py` — new `reresolve-sei` subparser (`--repo`, `--limit` default 200, `--resolve-sei/--no-resolve-sei`, `--loomweave-command`), reusing `_optional_sei_client` (cli.py:31). Fail-soft; emits JSON with loomweave posture. **Not** one of the 6 frozen tools.

**Tests — `tests/test_reresolve.py` (NEW):** null row → resolved when loomweave returns a SEI; **twin-collision** (resolved twin already exists, with and without a duplicate change_event) merges and deletes the orphan, survivor keeps resolved sei and merged first/last_seen; double-run is a no-op; loomweave absent → no rows mutated + `loomweave: unavailable`.

**Doctrine (SEI-orthogonality / honesty):** re-uses loomweave's minted SEI via `resolve_sei_for_locator`; never invents one. Sweep reports loomweave posture explicitly; absence never reads as "resolved".

### Rung 1d — Auto / lazy edge-snapshot capture

Today the hook only ingests, so `latest_snapshot` is None → `blast_radius` returns NO_SNAPSHOT. Hybrid: **lazy-on-read** (correctness floor) + **opportunistic-on-commit** (freshness).

**R7 — `blast_radius` stays pure (no new parameter).** Lazy capture lives entirely in the tool bodies.

**Changes:**
- `commands.py:impact_radius` and `reverify_worklist` — before computing blast radius, if `store.latest_snapshot(repo)` is None/SKIPPED **and** a loomweave client is available (decided by the existing `mcp.py`/`cli.py` dispatcher gate), attempt one scoped `capture_edge_snapshot(scope_locators=<resolved changed set>)`, then re-read `latest_snapshot`. If still missing (or no loomweave), fall through to the **unchanged** NO_SNAPSHOT path. Reuses existing `snapshot.py:capture_edge_snapshot` and its FULL/DELTA/SKIPPED honesty — new trigger, no new capture logic.
- `install.py:hook_body()` — append two fail-soft lines inside the managed block, after ingest:
  ```
  {executable} reresolve-sei --limit 25 >/dev/null 2>&1 || true
  {executable} capture-snapshot --commit HEAD >/dev/null 2>&1 || true
  ```
  (Bounded sweep heals incrementally; capture keeps the snapshot on HEAD so `commits_behind` stays 0.) Capture stays in the **hook**, not inside `ingest_commit` — keeps the per-tool-call loomweave latency (`loomweave.py:91` `timeout=10` **per tool call**, i.e. per entity) out of the commit critical path.
- **R5 — existing-hook migration:** `install_support.py:apply_git_hook()` already rewrites the managed block, so changing `hook_body()` reaches installed repos only via re-run. Add a `doctor` check "post-commit hook missing reresolve/capture lines" and have `--fix` reinstall the hook. Document: users run `warpline install --hooks` or `warpline doctor --fix` to pick up the new lines.
- `install_support.py:run_doctor` — add (non-fixable-by-default) checks: still-null SEI count, snapshot presence/staleness, hook-out-of-date. `--fix` runs an unbounded `reresolve-sei` + a `capture-snapshot` + hook reinstall.

**Tests — `tests/test_lazy_capture.py` (NEW):** impact_radius with no snapshot + fake loomweave client captures then returns a populated affected set; with no loomweave client, returns NO_SNAPSHOT unchanged (no error, no gate); `blast_radius` signature unchanged (pure). **`tests/test_install.py`** updated: hook body contains the two new fail-soft lines; doctor flags an old hook and `--fix` reinstalls.

**Doctrine (enrich-only / honesty):** capture is fail-soft and loomweave-conditional — absence falls through to honest NO_SNAPSHOT, never an error or a block. Existing completeness vocab preserved.

---

## RUNG 2 — Diagnostic capabilities + COP read surface

Four independent tracks. Ship **Track C first** (tracer bullet). All additive; zero frozen-contract mutation.

### Track C — Light up inert `risk`/`governance` enrichment (SHIP FIRST, ~15 LOC)

The federation block (`federation.entities[].risk/governance`) is never merged back into per-item `item.enrichment.risk/governance`, leaving them perpetually empty.

**Changes — `commands.py:reverify_worklist`** (after the `consult_federation` call, before overflow/page):
- Build `fed_by_locator` from `federation['entities']` keyed on locator. For each item, if its locator is present, copy `fed_entity['risk']` → `item['enrichment']['risk']` and `fed_entity['governance']` → `item['enrichment']['governance']`.
- **R6 scalar rule** (mirrors existing `work_state` at lines ~728-731): compute `risk_state`/`gov_state` —
  - `federation is None` (include_federation=False) or member `disabled`/`unreachable` → `"unavailable"`;
  - member reachable, no findings for any item → `"absent"`;
  - findings present → `"present"`.
- Pass `risk=risk_state, governance=gov_state` into the `enrichment_state()` call in `build_envelope`.
- `reverify.py` unchanged (its `_empty_enrichment()` scaffold is the correct target the merge fills).
- `mcp.py:_h_reverify` still passes `legis_client=None` — that single line is the only change when legis transport lands.

**Tests — `tests/test_enrichment_merge.py` (NEW):** with a fake wardline client returning findings, `item.enrichment.risk` is populated and envelope `enrichment.risk == "present"`; `include_federation=False` → `"unavailable"` (not `"absent"`); wardline reachable but empty → `"absent"`.

**Doctrine (D2 — proven-need):** this is the **demonstration that earns** freezing the wardline/legis inbound shape — not a pre-promised contract. Additive, reversible, advisory-only; does not lock the RESERVED-SHAPE inbound. Absence is explicit per the closed vocab.

### Track A — Co-change coupling graph (schema v3)

**Migration 3 DDL:**
```
CREATE TABLE IF NOT EXISTS co_change_pairs (
  repo_id          TEXT NOT NULL,
  entity_key_id_a  INTEGER NOT NULL,   -- canonical a < b
  entity_key_id_b  INTEGER NOT NULL,
  co_change_count  INTEGER NOT NULL,
  last_co_change   TEXT,
  last_commit_sha  TEXT,
  PRIMARY KEY (repo_id, entity_key_id_a, entity_key_id_b)
);
```
(Per-entity totals come from `change_events` aggregation at read time, so no `total_a/total_b` columns needed; if read cost demands it, add denormalized totals in a later additive migration.)

**Changes:**
- `coupling.py` (NEW) — `derive_pairs_from_commit(entity_key_ids) -> list[(a,b)]` (canonical a<b); `classify_confidence(co_change_count) -> 'low'|'medium'|'high'` (<5 low, 5–19 medium, ≥20 high); `coupling_rate(co_change_count, total) -> float|None` (None when total<5). No import from `commands`.
- `store.py` — `update_co_change_pairs(repo_id, commit_sha, entity_key_ids)` (one atomic upsert of all pairs); `co_change_partners(repo, entity_key_id, min_count=2) -> list[{entity_key_id, locator, sei, co_change_count, coupling_rate, sample_size, last_co_change}]` (joins `entity_keys` for SEI at read time).
- **R8 cap:** `update_co_change_pairs` skips pair generation when `len(entity_key_ids) > 30` and records nothing for that commit (high-fanout commits carry near-zero coupling signal). All co-change writes wrapped `try/except` fail-soft — never blocks ingest.
- `git.py:ingest_commit` + `backfill` — after `append_change_event`, call `update_co_change_pairs(...)` (fail-soft).
- `cli.py` — `rebuild-coupling` (rescans `change_events` grouped by `commit_sha`, idempotent, interruptible) and `co-change` (read surface for partners). Both read-only advisory.

**Tests — `tests/test_coupling.py` (NEW):** pair derivation canonical ordering; confidence thresholds; rate suppression <5; high-fanout commit (>30 entities) skipped; `rebuild-coupling` idempotent (run twice → same counts); SEI-sparse pairs emit `sei:null` + `enrichment.sei:absent`.

**Doctrine (SEI-orthogonality / no-mirror):** pairs keyed on warpline-local `entity_key_id` (a co-occurrence fact warpline owns, derived from its own `change_events`); SEI joined at read time, never minted, never mirrored. Honesty: rate suppressed + `confidence:low` below sample floor.

**D1/Q6 caveat:** co-change is **commit-keyed** now. Once the work-session episode boundary is ratified, the denominator/grouping must re-key to episode (two commits in one session = one co-change episode). Flagged as OPEN QUESTION Q6; re-key is an additive read-path change, not a schema break.

### Track B — Verification freshness (read-time compose, wardline-only first)

**Changes — `verification.py` (NEW):**
- `VerificationClient` Protocol: `last_verified_for_sei(sei) -> {verified_at, kind, actor, event_ref} | None`.
- **R10 — `WardlineVerificationClient` first** (wraps `WardlineDossierClient`): a `finding_state == 'resolved'` finding is a verification event. Ships now.
- `FiligreeVerificationClient` **deferred** behind confirming `closed_at` availability (Q4). Legis stays honestly `unavailable`.
- `compose_verification_freshness(last_changed_at, events) -> {verification_state: 'fresh'|'stale'|'unverified', last_verified_at, last_verified_kind, sources}` — `fresh` (verified ≥ changed), `stale` (verified < changed), `unverified` (no event). Never defaults to `fresh`.
- Surfaces in `item.enrichment.requirements[]` (the fourth frozen slot); envelope `enrichment.requirements` scalar follows the same R6 rule.

**Tests — `tests/test_verification.py` (NEW):** resolved wardline finding after last_changed → `fresh`; before → `stale`; none → `unverified`; wardline unreachable → `requirements: unavailable` (not `fresh`/`absent`).

**Doctrine (no-mirror):** composed at read time from sibling reads; warpline stores no `last_verified`.

### Track D — Temporal COP internals (`cop.py`; public surface INTERFACE-PENDING)

**R9 — new module `warpline/cop.py`** (imports `_consult_filigree/_wardline/_legis` from `federation.py`; `federation.py` never imports `cop.py`).

**Changes — `cop.py` (NEW):**
- `resolve_frame(store, repo, frame_spec) -> (items, frame_echo, warnings)` — dispatch on `frame_spec['kind']`: `rev_range`, `time_window`, `sei`, `branch_sha`, `edit`, using existing store methods (`list_change_events`, `resolve_ref`, `rev_range_commits`). `branch_sha` falls back to `rev_range` resolution **with a warning** until `detected_branch` (Rung 1b) is populated.
- `compose_temporal_cop(items, frame, *, work_client, risk_client, legis_client) -> {members, entities, coverage, frame}` — reuses the three `_consult_*` verbatim. `coverage = {members_consulted, members_total, dark_sectors: [members with reason_class disabled|unreachable]}`. **`consult_federation` is not modified.**

**Tests — `tests/test_cop.py` (NEW):** `resolve_frame` per kind (rev_range, sei resolve real items; branch_sha emits the fallback warning); `compose_temporal_cop` lists every member in `coverage` with correct `dark_sectors`; an unreachable member appears as `dark_sector`, never silently dropped.

**MCP/CLI wiring — DEFERRED to INTERFACE-PENDING.** When the public shape arrives: add `SCHEMA_TEMPORAL_COP` to `commands.py`, a `TOOL_SPECS` entry, `_h_cop` handler (`resolve_frame` → `compose_temporal_cop`), `_HANDLER_CONSUMES` entry; `assert_inputschema_consumed()` enforces correctness at import.

**Doctrine (enrich-only / honesty / frozen):** COP composes at read time, never gates; `dark_sectors` is the load-bearing coverage-honesty surface (unmonitored domain ≠ empty). New tool = new URI, never a mutation of a frozen v1 contract.

---

## INTERFACE PENDING — fill from user's concrete interface

Everything here is **blocked** on the user's concrete public surface for the correlation reads + COP. Design slots are prepared so each drops in additively without mutating a frozen v1 contract.

1. **COP public tool/CLI shape** (Track D wiring): MCP tool name, `inputSchema` (frame vocabulary + structure — which of rev_range/time_window/sei/branch_sha/edit are in scope, pagination strategy), output top-level fields beyond `{members, entities, coverage, frame}`. *Internals (`cop.py`) ship without it; only the `mcp.py`/`cli.py` handler waits.*
2. **Working-context anchor exposure on frozen read tools**: which frozen tool's response renders `detected_branch/head_sha/detected_at`, under which optional output field. *Capture + storage (Rung 1b) ship without it; output rendering waits.* Additive output fields only.
3. **Lazy auto-capture trigger policy** (Rung 1d): default-on vs gated by a new **optional** `auto_capture` input field on `impact_radius`/`reverify`. *Lazy machinery in the tool bodies is built; the default-on-vs-opt-in toggle and any new optional input property wait.*
4. **Verification-freshness record shape** inside `requirements[]` (Track B): the per-event dict (`verified_at/kind/actor/event_ref`) is placeholder until legis attestation transport defines its shape. *Wardline-sourced freshness ships now; the locked record shape waits.*
5. **Legis governance/attestation per-SEI read transport** (Track C governance dim + Track B legis source): no CLI/MCP exists. `_consult_legis` and the legis verification source stay honestly `unavailable` until it lands; the single `legis_client=None` line in `_h_reverify` is the only flip needed.

**What blocks on each:** (1) COP cannot be called by an agent. (2) Anchor data is captured but not yet visible to agents through a frozen tool. (3) Lazy capture cannot be defaulted-on or exposed as a toggle. (4) `requirements[]` event records cannot be frozen. (5) Governance enrichment + legis verification stay `unavailable`.

---

## OPEN QUESTIONS — confirm with the user

- **Q1 (Rung 0 naming):** `_enrichment.py`/`_blast.py` vs `_staleness.py`/`_resolver.py`? (Rename only; no structural impact.)
- **Q2 (Rung 1 hook cadence):** fire `reresolve-sei` + `capture-snapshot` on **every** commit, or throttle capture (e.g. only when `commits_behind` crosses a threshold) on high-commit-rate repos? Needs a commit-rate figure to tune.
- **Q3 (`detected_at` format):** ISO-8601 **UTC** assumed (matches `changed_at`). Confirm UTC vs local — affects cross-member temporal correlation later.
- **Q4 (filigree `closed_at`):** is `closed_at` already in filigree CLI issue JSON (then `FiligreeVerificationClient` ships now), or does it need a new filigree surface (then it's a cross-member negotiation, deferred)?
- **Q5 (episode granularity / D1):** confirm per-event anchor columns (v2) are acceptable as the substrate, with the work-session `change_episodes` table as a clean **v4 superset** — and ratify the work-session boundary semantics (dirty-tree / detached-HEAD / squash-rebase fallback) **before** any episode table is built.
- **Q6 (co-change re-key):** when the episode boundary is ratified, co-change must re-key from commit to episode (additive read-path change). Confirm commit-keying is acceptable as the interim.
- **Q7 (SEI merge survivor rule):** on twin-collision, keep the resolved-keyed `change_event` and drop the null-keyed duplicate (R11). Confirm this is the desired survivor and that dropping a null-keyed dup with differing `hunk_summary`/`actor` is acceptable.
- **Q8 (co-change backfill cost):** acceptable table size for the target repo? The >30-entity per-commit cap (R8) bounds it; confirm 30 is the right threshold (or a max-pairs-per-commit cap instead).
- **Q-sqlite:** confirm all deployment targets ship Python with bundled SQLite ≥ 3.35 (ALTER … DROP COLUMN rollback path); add a CI assertion.
- **Q-pyright:** after Rung 0 (~700 LOC), does pyright stop timing out on `commands.py`? If not, schedule the deferred SEAM-8 extraction as Rung 0.5.

---

## What I can start NOW vs what waits for the interface

**Start NOW (no interface dependency):**
- **Rung 0** in full (Steps 0.1–0.6) — pure refactor, unblocks everything.
- **Rung 1a** migration runner + PRAGMA hardening (prerequisite gate).
- **Rung 1b** anchor columns (v2) + `git.py` population + `store.py` read surfacing.
- **Rung 1c** SEI re-resolution sweep (`reresolve.py`, store merge core, `reresolve-sei` CLI — not a frozen tool).
- **Rung 1d** lazy-capture machinery in the tool bodies + hook lines + doctor checks (the *trigger* is built; default-on policy waits on item 3).
- **Rung 2 Track C** enrichment merge pass (tracer bullet — ship first).
- **Rung 2 Track A** co-change graph (v3) + `rebuild-coupling`/`co-change` CLI.
- **Rung 2 Track B** `verification.py` + `WardlineVerificationClient` (filigree/legis sources deferred).
- **Rung 2 Track D** `cop.py` internals (`resolve_frame` + `compose_temporal_cop`) and their unit tests.

**WAITS for the user's concrete interface:**
- COP public MCP tool/CLI wiring (`SCHEMA_TEMPORAL_COP`, `TOOL_SPECS`, `_h_cop`) — internals are ready; only the handler waits (item 1).
- Rendering the working-context anchor through a frozen read tool's output (item 2).
- Lazy auto-capture **default-on vs opt-in** decision and any new optional `auto_capture` input field (item 3).
- Freezing the `requirements[]` verification-event record shape (item 4).
- Legis governance/attestation inbound + the `_h_reverify` `legis_client` flip (item 5).
- Building the `change_episodes` (v4) table — waits on Q5 ratification, not on the public interface.