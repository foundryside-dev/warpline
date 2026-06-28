# Final Validation Gate — Cross-Document Consistency

**Validator:** analysis-validator (independent, evidence-based — final integration gate)
**Date:** 2026-06-28
**Target:** full Option-C package `docs/arch-analysis-2026-06-28-0728/` (`00`–`06` + `temp/`)
**Codebase:** `src/warpline/` @ HEAD `def6d43` (30 `.py`, 10,411 LOC)
**Scope of this gate:** cross-document **integration** — did the earlier per-document fixes propagate
everywhere, are facts/numbers stated consistently, do F↔D reconciliations and cross-references hold.
Per-document content was already validated upstream (catalog gate, architecture-critic, debt-cataloger)
and was **not** re-derived here.

> **Note on oracle:** loomweave has **no index** for this project right now (`./.weft/loomweave/loomweave.db`
> missing), so fan_in/fan_out graph metrics could not be re-queried. They were accepted as stated
> (consistent across all docs and matching the upstream catalog gate). All **dependency-edge** and
> **count** claims were re-verified directly against `src/` source — see evidence column.

---

## Overall Verdict: **PASS-WITH-FIXES**

**The package is shippable as-is.** The single biggest integration risk — that the corrected
dependency facts failed to propagate and a stale contradiction survived somewhere — is **clean**.
Every corrected edge (S2↔S3 back-edge; federation/install_support/dogfood no-longer-"stdlib-only";
cli→coupling; S8→S2) is stated consistently across `02`/`03`/`04`/`05` **and** confirmed against
source. All seven team-lead numeric facts are identical everywhere they appear. The F↔D reconciliation
(U1–U17) is complete and correct with no drops or mis-mappings.

What remains is **~6 one-line hygiene fixes**, all **Low** severity, none gating downstream use:
3 stale line-cites into the re-numbered catalog, one unqualified "no cycles" diagram caption, one
"3 migration-added tables" miscount (should be 2), one undisclosed diagram edge elision, and one
"three/four" prose miscount. No Critical, no High, nothing BLOCKs.

---

## Consistency Checks

| # | Check | Verdict | Evidence |
|---|-------|---------|----------|
| 1 | Corrected dependency facts confirmed in **source** | **PASS** | `store.py:1469` `from warpline.coupling import derive_pairs_from_commit` (+ comment `:1467-1468`), `store.py:1554` `coupling_rate`; `cli.py:136` `from warpline.coupling import classify_confidence`; `federation.py:38` `listing.reason` + `:39` `loomweave_resolve_qualnames`; `install_support.py:25` `store.WARPLINE_GITIGNORE_CONTENTS`; `dogfood.py:21` `snapshot`/`:22` `store`; `propagation.py:8`+`_blast.py:20` → `store` (S3→S2 half). |
| 2 | No stale "**stdlib only**" for federation / install_support / dogfood | **PASS** | `02:257-258` (S6) and `02:329-332` (S8) now list the real edges with explicit "*(Corrected from 'stdlib only' after validation.)*" notes. Remaining "stdlib only" hits are correct: `00:17` (runtime deps = 0), `02:221` (`loomweave.py` — **verified** zero `warpline` imports), and `siblings` (verified stdlib-only). |
| 3 | No stale "**single direction / zero cycles**" without the back-edge caveat | **PASS (1 caption nit → row 9)** | Caveat present in `02:6-13,359-368`, `03:115-121`, `04:24-26,57`, `05:197-205`. Module-acyclic vs subsystem back-edge distinguished consistently. Lone exception: the `03:75` caption (row 9). |
| 4 | S2↔S3 back-edge stated consistently across 02/03/04/05 | **PASS** | `02:6-13` & summary `02:351,366`; `03:108-109,118-119`; `04:24-26,57`; `05:199-203`. Same direction, same lines, same "lazy/deferred, module-acyclic" framing. |
| 5 | Numeric consistency (7 team-lead facts) | **PASS** | store **fan_in 38 / fan_out 0**: `00:23,02:70,03:116,05:66,04:57`. reverify **276 LOC / fan_out 34**: `00:24,01:141,02:185,04:29/95,05:13/43,06:39,debt:27`. **8 base tables**: `03:127,02:71-77,01;` verified `store.py:37,42,48,59,68,81,91,100`. **11 error codes + 11 subclasses**: `02:31` "11 subclasses", `01:110-111`, `04:60`; verified `errors.py` 11 `class …(WarplineError)` + `ERROR_CODES` frozenset = 11. **30 modules / 10,411 LOC**: consistent `00/01/02/04/05/debt`; verified `ls *.py`=30, `wc`=10411. **4/5**: `05:9,06:19,00:63`. **1 High debt item**: `debt:D2`, `05` (2 High *quality* findings F1/F2 ≠ debt severity — see row 10). |
| 6 | F↔D reconciliation — team-lead spot-checks | **PASS** | `06:35-50`: **U1=F6+D2** (High, FK-less) ✓; **U2=F5** (critic-only) ✓; **U5=F1+D3** ✓; **U6=F2+D1** ✓. |
| 7 | F↔D reconciliation — **full coverage** (no dropped findings) | **PASS** | All **F1–F11** map: F1→U5, F2→U6, F3→U3, F4→U4, F5→U2, F6→U1, F7→U11, F8→U10, F9→U14, F10→U15, F11→U8. All **D1–D12** map: D1→U6, D2→U1, D3→U5, D4→U7, D5→U9, D6→U3, D7→U12, D8→U13, D9→U10, D10→U16, D11→U15, D12→U8. No mis-mappings; U17 = housekeeping (test_attest false-positives). |
| 8 | Cross-references resolve (file-level) | **PASS** | `04:125-133` "how to read" table → all targets exist (`01`,`02`,`03`,`05`,`06`,`temp/validation-*`,`temp/debt-catalog`). `06:135-137` pointers exist. `05:5` → `01`,`02` exist. (Line-level cites: row 11.) |
| 9 | `03:75` "no cycles" caption | **FIX (Low)** | Row 9 below. |
| 10 | Quality "2 High" vs debt "1 High" not contradictory | **PASS** | Different axes, stated as such: `05` rates **2 High** *maintainability/testability* findings (F1/F2); `debt:D2` is the **1 High** *data-integrity* item. `06:20` reconciles: "1 High (data-integrity, D2/F6) · ~6 Medium · ~6 Low." Not a numeric conflict. |
| 11 | Line-level cross-references into the re-numbered catalog | **FIX (Low)** | Rows 11a–11c below. |
| 12 | Diagram matches catalog (L3 edges vs dependency summary) | **FIX (Low)** | Row 12 below — one undisclosed elision. |
| 13 | `03:127` table count | **FIX (Low)** | Row 13 below. |
| 14 | `06` prose item count | **FIX (Low)** | Row 14 below. |
| 15 | Contract conformance — Option-C deliverables present + structured | **PASS** | `00`–`06` all present; `temp/validation-catalog.md` + `temp/debt-catalog.md` present. Each carries its required structure (catalog: 8 entries × full field set; quality: verdict + per-component table + F1-F11 + Confidence/Risk/Gaps/Caveats; handover: verdict recap + F↔D table + sequence; debt: inventory + top-5 + Confidence/Risk/Gaps/Caveats). |

---

## Stale Contradictions

**The team-lead's #1 concern is essentially clean.** Exactly **one** residual instance of the
"unqualified no-cycles" pattern survives, and it is self-correcting within its own section:

### Row 9 — `03-diagrams.md:75` unqualified "no cycles" on the C4 L3 **subsystem** diagram — **Low**
- **Exact location:** `03-diagrams.md:75` — *"Layered flow toward the foundation; no cycles."*
- **Contradiction:** This caption sits directly above the C4 L3 **subsystem** diagram, which (a) draws
  the dotted `store→coupling` / `cli→coupling` back-edges (`03:108-109`) and (b) carries a note 43
  lines down (`03:118-119`) stating *"the subsystem graph has a real `store`↔`compute` cycle."* The
  caption asserts the opposite of the diagram's own note. It is the verbatim instance of the
  "zero cycles without the S2↔S3 caveat" pattern the gate was told to hunt — it just happens to be
  contradicted in-section rather than left standing.
- **Fix:** qualify the caption, e.g. *"Layered flow toward the foundation; **module-acyclic** (the
  dotted edges are the one subsystem-level S2↔S3 back-edge)."*

No other stale "stdlib only" / "single direction" / "zero cycles" contradiction exists anywhere in the
package. (Checks 2–4 all PASS, source-confirmed.)

---

## Mis-mappings (F↔D Reconciliation)

**None.** The U1–U17 table is complete and correct (checks 6 + 7). The four named spot-checks verified,
and every F1–F11 and D1–D12 maps with no drops and no mis-mappings.

One **prose** inaccuracy (the table itself is correct):

### Row 14 — `06-architect-handover.md:30` "three items" miscount — **Low**
- **Exact location:** `06:30` — *"the critic added **three** items the debt pass didn't (F4, F5, F7,
  F9)…"* — lists **four** items (F4, F5, F7, F9) but says "three." These are exactly the four
  critic-only rows (U2/U4/U11/U14 carry "—" in the Debt column), so **four** is correct.
- **Secondary (same sentence):** the companion clause "*the debt pass added items the critic folded
  into prose (D4, D5, D7, D8, D10)*" is loose — D4 (Focus 5) and D7 (S8 table row) *are* in `05` prose,
  but D5/D8/D10 are genuinely debt-only and not in the critic's prose. The **table** correctly marks
  them Critic="—"; only the prose characterization overreaches. Fix the count to "four"; optionally
  tighten the prose clause.

---

## Broken / Stale Cross-References

**Root cause (single):** the catalog was re-numbered when the upstream fixes were applied (it gained a
methodology-caveat block at `02:15-18`, an expanded back-edge paragraph `02:6-13`, and corrected
S1–S5 dependency prose). All downstream line numbers shifted **down ~13–17 lines**. Three inbound
line-cites that were authored against the *pre-fix* catalog were never re-synced — so they now point at
the **wrong content**. The prose at each citing site is accurate; only the line pointer drifted.

### Row 11a — `05:252` (F10) → `02:40-42` is stale — **Low**
- **Cited:** `02-subsystem-catalog.md:40-42` for "*`apply_overflow` writes a file … side-effect-free
  contract module (S1)*."
- **Reality:** `02:40-42` is the `_enrichment.py` / `locators.py` Key-Components bullets. The
  `apply_overflow` overflow-spill **Concern** is now at **`02:53-55`**.
- **Fix:** retarget to `02:53-55`.

### Row 11b — `05:262` (F11) → `02:211-213` is stale — **Low**
- **Cited:** `02-subsystem-catalog.md:211-213` as where the catalog "*flags it*" (the hand-rolled
  loomweave stdio JSON-RPC client risk).
- **Reality:** `02:211-213` is the `loomweave.py` Key-Components bullet (defines the `ToolClient` port)
  + the start of the `git.py` bullet. The loomweave-client **Concern** is now at **`02:228-230`**.
- **Fix:** retarget to `02:228-230`.

### Row 11c — `temp/debt-catalog.md:35` (D11) → `02:40-42` is stale — **Low**
- **Cited:** `../02-subsystem-catalog.md:40–42` for the same `listing.py` overflow-spill concern.
- **Reality:** same as 11a — concern is at **`02:53-55`**.
- **Fix:** retarget to `02:53-55`.

---

## Other Numeric / Diagram Findings

### Row 13 — `03-diagrams.md:127` "3 migration-added tables" should be **2** — **Low**
- **Location:** `03:127-128` — *"8 base tables … + **3 migration-added tables** (`co_change_pairs` v3,
  `verification_events` v4; anchor columns v2 on `change_events`)."*
- **Issue:** Only **2** of the three listed items are tables; v2 added **columns** (`detected_*`) to
  `change_events`, not a table. Verified: `store.py` has exactly 10 `CREATE TABLE` (8 base + `co_change_pairs:184`
  + `verification_events:212`). The doc's **own ER diagram** (`03:133-153`) draws **10** tables, i.e.
  2 migration-added — contradicting the "3" in its own prose.
- **Fix:** *"+ 2 migration-added tables (`co_change_pairs` v3, `verification_events` v4) + v2 anchor
  columns on `change_events`."*

### Row 12 — `03` L3 diagram omits the `S8→S7` edge the catalog records, **undisclosed** — **Low**
- **Location:** `03:88-110` draws `S7→S8` but **not** `S8→S7`. The catalog records `S8→S7`
  (`dogfood`→`mcp.dispatch`) in S8 outbound (`02:329`) and as an intentional upward reach (`02:367`);
  confirmed in source at **`dogfood.py:20`** `from warpline.mcp import dispatch`.
- **Issue:** The diagram **discloses** its S7→S5/S6 elision (`03:121`) but is silent about omitting
  `S8→S7`. Drawing it would make the `S7↔S8` subsystem round-trip visible (module-acyclic, since
  `mcp.py` imports neither `cli` nor `dogfood`) — which is also why the row-9 "no cycles" caption reads
  cleaner than reality. Almost certainly an intentional readability elision, **not** an error in the
  catalog — but it should be disclosed like the other one.
- **Fix:** add `S8→S7` to the elision note, or draw it dotted with a one-line caption.

---

## Confidence Assessment

**Overall confidence: High** on the integration verdict.
- **High** on all dependency-edge claims (row 1) and all count claims (row 5): each rests on a directly
  re-read `src/` `import` statement or a re-counted construct (`errors.py`, `store.py` DDL, `ls`/`wc`),
  not on the (currently-unavailable) loomweave oracle.
- **High** on the F↔D coverage map (rows 6–7): built by reading `05` F1–F11, `temp/debt-catalog` D1–D12,
  and the `06` U-table end-to-end and matching every row both directions.
- **High** on the three stale cross-references (rows 11a–c) and the `03:127`/`03` L3 findings (rows
  12–13): confirmed by reading the cited target lines directly.
- **Medium-High** on fan_in/fan_out figures themselves (row 5): re-derivation was impossible
  (no loomweave index); accepted as internally consistent + matching the upstream catalog gate, which
  verified them against a then-fresh index.

## Risk Assessment

- **If shipped unfixed:** impact is **cosmetic-to-navigational**. An architect following `05` F10/F11 or
  `debt` D11 to the cited catalog lines lands on the wrong bullet (rows 11a–c); a reader trusting the
  `03:75` caption or the `03:127` "3 tables" count over the adjacent diagram is briefly misled. None
  changes a finding, severity, count, or recommendation. **Low downstream risk.**
- **No correctness risk to the analysis conclusions:** the substance (the S2↔S3 back-edge, the FK-less
  High item, the two god-units, the 4/5 verdict, the U1–U17 backlog) is internally consistent and
  source-confirmed.
- **Residual oracle risk:** fan_in/fan_out (38/0, 34) were not independently re-derived (no index). If
  an exact re-count is required, run `loomweave analyze .` and re-query — but these matched the prior
  gate and are not load-bearing on any verdict.

## Information Gaps

- **loomweave index absent** → graph metrics (fan_in 38, fan_out 0, fan_out 34) accepted as stated, not
  re-derived. Dependency *edges* were instead verified by direct source import-extraction (stronger
  ground truth for the edge claims).
- **Per-document technical accuracy** (whether the patterns, severities, and recommendations are
  *correct*) was **out of scope** for this gate and was covered by the upstream architecture-critic /
  debt-cataloger passes. This gate checked integration, not re-adjudication.
- I did not re-verify every line-cite in `05`/`06`/`debt` into `src/` exhaustively; I targeted the
  inter-document cites (into `02`) the task named, plus a sample of source cites. Intra-doc source
  cites were spot-checked, not swept.

## Caveats

- This is a **structural / consistency** gate: contract conformance, cross-document agreement,
  numeric/edge consistency, reference integrity. It does **not** re-judge subsystem boundaries, pattern
  correctness, or finding completeness.
- All six fixes are **Low** and **non-blocking**. PASS-WITH-FIXES means: ship now, apply the hygiene
  fixes opportunistically. They cluster into one mechanical pass: retarget 3 line-cites to the
  re-numbered catalog, qualify 1 caption, correct 2 counts, disclose 1 elision.
- The fixes are deliberately *not* applied by this gate (validation ≠ authoring). Recommend the
  coordinator apply them in `02`-citing docs (`05:252,262`; `debt:35`), `03` (`:75,:127`, L3 note), and
  `06` (`:30`).
