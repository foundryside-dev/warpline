# Validation Report — 02-subsystem-catalog.md

**Validator:** analysis-validator (independent, evidence-based)
**Date:** 2026-06-28
**Target:** `docs/arch-analysis-2026-06-28-0728/02-subsystem-catalog.md`
**Supporting:** `docs/arch-analysis-2026-06-28-0728/01-discovery-findings.md`
**Codebase:** `src/warpline/` @ HEAD `def6d43` (30 `.py`, ~10.4k LOC)
**Loomweave index:** `fresh`, analyzed at `def6d43` (matches HEAD) — graph metrics are trustworthy.

---

## Overall Verdict: **PASS-WITH-FIXES**

The 8-subsystem decomposition is sound, module assignments are defensible (no misfiles found), and **every spot-checked numeric/factual claim verified true against source.** However, the **dependency-direction summary contains a cluster of real, surgical inaccuracies** — the catalog repeatedly asserts "stdlib only / no internal deps" for modules that have plainly-visible internal imports. These are not cosmetic: they propagate directly into the diagram phase (which will draw the subsystem graph wrong) and the architecture-critique phase (which will miss a genuine `store → coupling` coupling smell). The dependency-section corrections are marked **REQUIRED**, not optional.

This is not a BLOCK: the decomposition itself is correct, there is no module-level import cycle, and the fixes are enumerable edits to the dependency prose + summary diagram.

---

## Checks Actually Run (so a zero-misfile result is justified)

1. **Coverage** — enumerated all 30 `.py` files vs. the 29 catalogued modules.
2. **Module assignment** — read module docstrings/headers for `locators`, `coupling`, `_attest`, `federation`, `siblings`, `snapshot`, `reverify`, `verification` (the borderline + representative set) and cross-checked role vs. assigned subsystem.
3. **Dependency direction** — extracted every intra-package / sibling `import` statement from all 30 modules (`grep` of import blocks) and mapped importer→imported to subsystem edges; cross-checked against loomweave `entity_neighborhood_get`, `entity_coupling_hotspot_list`, `module_circular_import_list`.
4. **Claim verification** — confirmed/refuted 11 specific factual claims with file:line citations (table below).
5. **Contract conformance** — checked all 8 entries for the required field set.

---

## Claims Table

| # | Claim (from catalog / task) | Verdict | Evidence |
|---|---|---|---|
| 1 | `store.py` fan_in 38, fan_out 0 | **CONFIRMED** *(as loomweave metric)* | `entity_coupling_hotspot_list` → `warpline.store` fan_in 38 / fan_out 0. NB: loomweave does not count function-body imports (see #2). |
| 2 | `store.py` → "stdlib only (no internal deps — this is *why* it can be the foundation)" | **REFUTED** | `store.py:1469` `from warpline.coupling import derive_pairs_from_commit`; `store.py:1554` `from warpline.coupling import coupling_rate`. Two deferred (function-local) imports of `coupling` (S3). In-code comment at `store.py:1467-1468`: *"store -> coupling is the one-way edge."* |
| 3 | `reverify_worklist` 276 LOC, fan_out 34 | **CONFIRMED** | `commands.py:793-1069` (= 276 lines, loomweave `source_line_start/end`); `entity_coupling_hotspot_list` fan_out 34. |
| 4 | No circular imports (`module_circular_import_list`) | **CONFIRMED** *(module level)* | `module_circular_import_list` → `cycles: [], total: 0`. True because `coupling` imports nothing, so `store→coupling` forms no module cycle. (Does **not** clear the subsystem-level back-edge — see Finding A.) |
| 5 | 8 base SQLite tables: meta/repos/entity_keys/commit_refs/change_events/edge_snapshots/snapshot_edges/health_log | **CONFIRMED** | `store.py:37,42,48,59,68,81,91,100` — exactly these 8 in frozen `SCHEMA`. `co_change_pairs` (`:184`, v3) and `verification_events` (`:212`, v4) are migration-added, correctly distinguished by the catalog. |
| 6 | 11 closed error codes, 3 retryability values | **CONFIRMED** | `errors.py:9-23` `ERROR_CODES` frozenset = 11 codes; `errors.py:8` `RETRYABILITY` = 3 values. |
| 7 | "WarplineError base + **10** subclasses" | **PARTIALLY REFUTED (LOW)** | `errors.py` defines **11** subclasses (`:70,76,83,90,97,104,111,118,124,130,136`). Base + `InternalError` share `internal_error`, so 11 subclasses pin 11 codes. Count is off by one. |
| 8 | `co_change_pairs` has no FOREIGN KEY | **CONFIRMED** | `co_change_pairs` DDL `store.py:184-192` — PRIMARY KEY only, no FK. |
| 9 | `snapshot_edges` has no FOREIGN KEY | **PARTIALLY REFUTED (LOW)** | `snapshot_edges` **has** `FOREIGN KEY(snapshot_id) REFERENCES edge_snapshots(id)` at `store.py:98`. It has **no** FK on its `source_entity_key_id`/`target_entity_key_id` columns (`:93-94`). Catalog's *nuanced* wording ("key on entity_key_id integers with no FOREIGN KEY") is defensible; its **bolded** "No DB-level FKs on derived tables" overstates. Concern substance (manual referential integrity in merge path, `store.py:891-1042`) is **correct**. |
| 10 | `cli.main` fan_out 31 | **CONFIRMED** | `entity_coupling_hotspot_list` → `warpline.cli.main` fan_out 31. |
| 11 | `listing.reason` fan_in 16 | **CONFIRMED** | `entity_coupling_hotspot_list` → `warpline.listing.reason` fan_in 16. |

---

## Dependency-Direction Findings (wrong / missing edges)

All edges below are **plainly-visible top-level imports** unless marked "(deferred)". The catalog header states dependencies were "derived from import blocks + the loomweave edge graph," so the top-level omissions are self-inconsistent with the catalog's own stated method.

### Finding A — `store`(S2) → `coupling`(S3): unacknowledged subsystem back-edge **[REQUIRED]**
- **Evidence:** `store.py:1469`, `store.py:1554` (deferred imports of `warpline.coupling`).
- **Refutes three catalog statements:**
  1. S2 outbound: *"store.py → stdlib only (no internal deps)"* (§S2 Dependencies).
  2. Summary diagram: `S2 Store … ──► (store: none / snapshot: S5)`.
  3. Closing claim: *"the only 'upward' reaches are S8→S7 and S3→S6 … both intentional and acyclic."*
- **Two-granularity framing (so it is neither overstated nor softened):**
  - *Module level:* **no cycle** — `coupling` is a pure leaf (imports nothing); `module_circular_import_list = 0` confirms it. The catalog is right about this.
  - *Subsystem level:* `store`(S2)→`coupling`(S3) **plus** `propagation`(S3)→`store`(S2) (`propagation.py:8`) and `_blast`(S3)→`store`(S2) (`_blast.py:20`) = a real **S2↔S3 back-edge**. The "single direction of flow toward the foundation, zero cycles" narrative does not hold at subsystem granularity.
- **Why it matters downstream:** a "foundation" persistence module reaching *up* into the pure-compute layer is exactly the coupling smell the architecture-critique phase needs surfaced. The catalog author missed what `store.py`'s author documented in a comment.

### Finding B — `federation`(S6) → `listing`(S1) + `loomweave`(S5): "stdlib only" is wrong **[REQUIRED]**
- **Evidence:** `federation.py:38` `from warpline.listing import reason` (S1); `federation.py:39` `from warpline.loomweave import loomweave_resolve_qualnames` (S5).
- **Refutes:** S6 outbound *"stdlib only (urllib … subprocess …)"* and summary diagram `S6 Federation … ──► stdlib`.
- These are **top-level** edges the loomweave graph contains, so this contradicts the catalog's stated derivation method — not a deferred-import artifact.
- **Knock-on:** S5's inbound list (§S5 Dependencies) and the summary diagram `S5 Seams ◄── S2,S3,S4,S7,S8` both **omit S6→S5**. Add `S6` to S5's inbound.
- NB: `siblings`(S6) *is* genuinely stdlib-only (`siblings.py` imports only `json/os/urllib/...`); the error is specific to `federation`.

### Finding C — `install_support`(S8) → `store`(S2): "stdlib" is wrong **[REQUIRED]**
- **Evidence:** `install_support.py:25` `from warpline.store import WARPLINE_GITIGNORE_CONTENTS` (S2); also `:24` `install` (S8 intra), `:23` `__version__`.
- **Refutes:** S8 outbound *"install_support/install → stdlib"*.

### Finding D — `dogfood`(S8) → `store` + `snapshot`(S2): missing S8→S2 **[REQUIRED]**
- **Evidence:** `dogfood.py:22` `from warpline.store import WarplineStore, default_store_path`; `dogfood.py:21` `from warpline.snapshot import capture_edge_snapshot` (S2).
- **Refutes:** S8 outbound list and summary diagram `S8 Lifecycle … ──► S4,S5,S7` — both omit **S2**.

### Finding E — `cli`(S7) → `coupling`(S3): missing S7→S3 **[REQUIRED]**
- **Evidence:** `cli.py:136` `from warpline.coupling import classify_confidence` (deferred, inside a function).
- **Refutes:** S7 outbound list and summary diagram `S7 Surfaces … ──► S1,S2,S4,S5,S6,S8` — both omit **S3**.

### Finding F — S1 inbound "all other subsystems" is overstated; S1 and S2 are *parallel*, not stacked **[RECOMMENDED]**
- **Evidence:** No module in S2 imports any S1 module — even transitively. `store`→`coupling`→∅; `snapshot`→`loomweave`(S5)/`store`(S2)→… none reach S1. S8 likewise imports no S1 module directly (`install_support`→`store`/`install`/`__version__`; `dogfood`→S4/S5/S2/S7; `productization`/`install`→stdlib).
- **Refutes:** §S1 Dependencies *"Inbound: **all** other subsystems."* Actual S1 inbound = {S3, S4, S5, S6, S7}. S2 and S8 are absent.
- **Sharper statement than "the word 'all' is wrong":** the linear ordering **"S1 → S2"** is unsupported — the store layer does not sit on the contract layer. S1 and S2 are **parallel foundations**, both depended on by higher layers. (`listing.reason` fan_in 16 remains correct and is the right evidence for S1's centrality.)

### Finding G — "imports seam *ports*" is euphemistic **[LOW]**
- **Evidence:** `reverify.py:7` imports concrete functions `priority_from_work, work_enrichment_for_sei` from `siblings`, not only the `WorkClient` Protocol. The S3→S6 edge is real (catalog flags it) but it is not purely a port import.

---

## Module Assignment Spot-Check (docstring-based)

Read module docstrings/headers; mapped stated role → assigned subsystem.

| Module | Stated role (docstring) | Assigned | Verdict |
|---|---|---|---|
| `coupling` | "Temporal co-change coupling derivation (Rung 2 Track A). Pure derivation helpers." | S3 | ✅ correct |
| `_attest` | "Risk-as-verification consumer … pure, enrich-only … no store, no git, no I/O." | S3 | ✅ correct |
| `verification` | "Pure verification-freshness compute … no store, no git, no I/O." | S3 | ✅ correct |
| `reverify` | worklist render; imports `listing`(S1)+`siblings`(S6) | S3 | ✅ correct (see Finding G) |
| `federation` | "reverify's cross-member consult (HARD SEAM)" filigree/wardline/legis | S6 | ✅ correct |
| `siblings` | filigree HTTP work seam (urllib, stdlib) | S6 | ✅ correct |
| `snapshot` | neighborhood→`snapshot_edges` rows; `NeighborhoodClient` port | S2 | ✅ correct (bridge S5→S2) |
| `locators` | `python_entity_locators(path, source)` — pure AST locator extraction, no docstring | S1 | ⚠️ **borderline** |

**No hard misfiles found.** `locators` is the one soft case: it is a pure, dependency-free AST helper whose only consumer is `git`(S5) ingestion (`git.py:9`). Semantically it is an ingestion/resolution helper, not a "wire contract" element, so S5 would be a defensible alternative home. Grouping it with S1's pure foundation leaves is acceptable; flagging it as borderline rather than wrong.

---

## Coverage

- **29 of 30** modules are placed across the 8 subsystems.
- **Uncatalogued:** `__init__.py` (11 LOC) — the package marker exposing `__version__`, imported by `envelope`(S1), `install_support`(S8), `cli`, `mcp`. Excluding a package `__init__` is conventional and acceptable, but it should be **explicitly acknowledged** (one line) rather than silently dropped, since it is a real import target. **[LOW]**
- `py.typed` is a 0-byte marker (not a module) — correctly excluded.

---

## Contract Conformance

All 8 subsystem entries (S1–S8) carry the required field set: **Location, Responsibility, Key Components, Dependencies (inbound + outbound), Patterns Observed, Concerns, Confidence.** Layer-order header and subsystem-level dependency summary are present. **PASS** on structure. (The defects above are accuracy-of-content, not missing-field, issues.)

---

## Prioritized Required Fixes

**REQUIRED (block the diagram + critique phases if left):**
1. **Finding A** — Correct S2 outbound: `store → coupling` (S3) exists (`store.py:1469,1554`). Remove "stdlib only / no internal deps"; update the summary diagram `(store: none)`; add `store→coupling` to the "upward reaches" list; reconcile the "zero cycles" claim by distinguishing module-level (acyclic) from subsystem-level (S2↔S3 back-edge).
2. **Finding B** — Correct S6 outbound: `federation → listing`(S1) + `loomweave`(S5). Replace "stdlib only." Add `S6` to S5's inbound list and the summary diagram.
3. **Finding C** — Correct S8 outbound: `install_support → store`(S2). Replace "stdlib."
4. **Finding D** — Add `S2` to S8 outbound (`dogfood → store/snapshot`) in both the prose and the summary diagram.
5. **Finding E** — Add `S3` to S7 outbound (`cli → coupling`) in both the prose and the summary diagram.

**RECOMMENDED:**
6. **Finding F** — Rewrite S1 inbound from "all other subsystems" to the actual set {S3,S4,S5,S6,S7}; note S1 and S2 are parallel foundations, not stacked.

**LOW (fix opportunistically):**
7. Claim #7 — "10 subclasses" → 11.
8. Claim #9 — reword "No DB-level FKs on derived tables" → "no FK on the `entity_key_id` columns" (snapshot_edges has a `snapshot_id` FK).
9. Coverage — add one line acknowledging `__init__.py` is intentionally uncatalogued.
10. Finding G — soften "imports seam *ports*" (reverify imports concrete `siblings` functions too).

---

## Confidence Assessment

- **High** confidence in all REFUTED/CONFIRMED claims in the table and Findings A–E: each rests on a direct file:line import statement or a loomweave graph metric from a *fresh* index at the analyzed HEAD.
- **High** confidence in "no hard misfiles" — backed by docstring reads (the method the task named), not inference alone.
- **Medium-High** on Finding F's "parallel foundations" framing — verified S2 imports no S1 module directly and traced its transitive closure (`store→coupling→∅`, `snapshot→loomweave/store`), but did not exhaustively walk every S8 transitive path beyond the direct importers.

## Risk Assessment

- **If shipped unfixed:** the diagram phase will render an incorrect subsystem dependency graph (missing S6→S5, S8→S2, S7→S3; false "store: none"), and the architecture-critique phase will **miss the `store→coupling` back-edge** — the single most architecturally-interesting finding here. Medium downstream risk; low correctness risk to the code itself (the code is fine; only its description is off).
- **Verdict risk:** PASS-WITH-FIXES (not BLOCK) is appropriate — decomposition and all metrics hold; defects are enumerable and localized to the dependency narrative.

## Information Gaps

- **"2667 edges"** (catalog header) vs. loomweave's reported **3545** total edges (`project_status_get`): plausibly a filtered subset (post-`heddle.*`-tombstone, resolved-confidence only, or import-only), but the exact filter is **unverifiable from available data**. Descriptive flourish; not load-bearing. Noted, not blocking.
- **"WarplineStore — 40 methods"**: not independently re-counted (outside the task's named spot-checks); accepted as-is.
- Subsystem-level edge claims were validated by direct `import` extraction + targeted loomweave neighborhoods, not a full all-pairs graph diff.

## Caveats (scope of this validation)

- I validate **structural / evidence-based accuracy**: contract conformance, cross-document consistency, dependency-direction correctness against actual imports, and the specific factual claims spot-checked. Scope was `src/warpline/` only.
- I do **not** adjudicate whether the subsystem *boundaries* are the architecturally-optimal decomposition, whether the identified *patterns* are the right abstractions, or whether the *concerns* are complete — those require the architecture-critic / refactoring-architect phase.
- loomweave's edge graph is authoritative for resolved static imports but **does not capture function-body (deferred) imports** — the root cause of the `store→coupling` and `cli→coupling` omissions. Where the graph and source disagree, I cite **source** as ground truth.
