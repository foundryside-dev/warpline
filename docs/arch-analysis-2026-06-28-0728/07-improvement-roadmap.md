# Improvement Roadmap

**Source:** `docs/arch-analysis-2026-06-28-0728/` — `06-architect-handover.md` (unified U1–U17),
`temp/debt-catalog.md` (D1–D12), `05-quality-assessment.md` (F1–F11)
**Created:** 2026-06-28
**Scope:** `src/warpline/` at HEAD `def6d43` (30 modules, ~10.4k LOC)
**Security Priority Maintained:** ✅ (no critical/high security debt exists — see Phase 1)

> **Read this first.** This is a **4/5, healthy, contract-first system with zero shipping defects.**
> Every item below is *future-edit hazard reduction*, not firefighting. Nothing here produces a wrong
> answer to a user **today**. The roadmap is risk-class ordered per the immutable priority hierarchy
> (Security → Reliability → Architecture → Performance → Quality); it deliberately does **not** adopt
> the handover's value×effort wave ordering as the *priority*, though cheap one-liners are flagged to
> ride along in execution (§ Priority Adjustments).

---

## Phase 1: Critical & High Security (0 weeks — NONE FOUND)

**Goal:** Eliminate critical and high security vulnerabilities.

**Result: no critical or high security findings exist.** This is itself a verified finding, not an
unexamined gap. The architecture-critic and debt passes both certified a clean posture by exhaustive
evidence:

- **Zero runtime dependencies** (`pyproject.toml:24`) — no supply-chain surface.
- **No shell execution anywhere** — exhaustive grep for `shell=True` / `os.system` / `os.popen`
  returned none; every subprocess uses an argv list (`federation.py:77,176`, `loomweave.py:52,155`,
  `git.py`).
- **SQL fully parameterized** — the only string interpolation into SQL is the int-coerced
  `PRAGMA user_version = {int}`; everything else is bound parameters.
- **Threat model is local-first, single-tenant** — the "attacker" is already the local CLI/MCP caller.

The single security-*adjacent* item is **U14 / F9** (read-only git verbs lack a `--` end-of-options
terminator, `git.py:39-43,95,109-114,130`). It is a **Low defense-in-depth hardening nit** — an
argument-injection residual (a ref starting with `-` consumed as a git flag) on read-only verbs with
no code-execution primitive, explicitly rated as *not* moving the score. It is **not** inflated into a
security phase; it is sequenced into Phase 5 (Quality/Hygiene) where its severity places it.

**Phase 1 Exit Criteria:**
- [x] No SQL injection (fully parameterized SQL — verified)
- [x] No shell/command injection (no `shell=True`/`os.system`/`os.popen`; argv-list throughout — verified)
- [x] No supply-chain exposure (zero runtime deps — verified)
- [x] No auth/authorization surface in the local-first single-tenant model (N/A by design)
- [x] Security-adjacent hardening (U14) identified and scheduled (Phase 5), not deferred silently

---

## Phase 2: System Reliability & Correctness (~1 week)

**Goal:** Eliminate the items that can silently produce a *wrong answer*, silently *corrupt data* on a
future edit, or silently *degrade in the field*. This is the highest **present** risk class and it is
**cheap** — four of the five items are S/M effort.

### 2a. U2 — Eliminate the unenforced positional invariant `_blast`↔`commands` (S–M, **Medium / highest residual risk**)
**Evidence:** `commands.py:836-843` builds `changed_key_ids`/`affected_key_ids` by **position** and
aligns them positionally to the frozen `changed`/`affected` views (which drop `entity_key_id` for
SEI-orthogonality). Correctness depends on `enrich_blast` (`_blast.py:142-159`) iterating the same
lists in the same order with no filter — enforced **only** by code comments.
**Risk if not fixed:** This is the **only** finding that can fail *silently incorrect* — a future edit
that filters one side but not the other misattaches the **wrong verification-freshness state to the
wrong entity**, with no exception, caught only by a test that happens to exercise a filtered case.
**Effort:** S–M. Carry `entity_key_id` in a private (non-frozen) field so alignment is by-key not
by-index; or assert `len()` equality + per-row id echo so divergence fails loudly.
**Dependencies:** None. Do first — it is the only silent-wrong-answer risk in the system.

### 2b. U1 — Post-merge referential-integrity invariant on the FK-less derived tables (M, **High / only data-integrity item**)
**Evidence:** `co_change_pairs` (`store.py:182-194`) and `snapshot_edges` (`store.py:91-99`) key on
`entity_key_id` with **no** FK; integrity across a SEI re-resolution merge is maintained entirely in
Python (`_merge_into_twin` `store.py:831-901`, `_repoint_co_change_pairs` `:903-990`,
`_repoint_snapshot_edges` `:992-1054`). `PRAGMA foreign_keys=ON` (`store.py:652`) gives no backstop on
those columns.
**Risk if not fixed:** A future edit to the ~270-LOC merge family — or a third `entity_key_id`-keyed
table — can **silently orphan rows / corrupt the graph** with no DB-level backstop. The implementation
is correct today; the *fragility* is that ~270 LOC of hand-surgery replaces what a constraint would
enforce for free.
**Effort:** M. Do **NOT** naively add FK/CASCADE — it would fire mid-merge and break the *intentional*
SEI-orthogonal repoint (`store.py:177`). Add a `_assert_no_orphans` debug/CI invariant + a property
test that runs the full merge family against a fixture and asserts every `*_entity_key_id` resolves.
Converts silent corruption into a loud test failure.
**Dependencies:** None now; **pairs naturally** with the `store_identity_merge.py` extraction in
Phase 3 (3a) — do the invariant first so the extraction is gated by it.

### 2c. U3 + U4 — Read-path observability + close the lazy-capture throttle gap (S, **Medium**, bundled — genuine overlap)
**Evidence:** Three read-path swallows discard the exception with no trace — `session_context`
(`commands.py:77`), `_lazy_capture_if_missing` (`:674`), `_attest_content_hashes` (`:707`); the
`# noqa: BLE001` annotations are **inert** (BLE is not in `ruff` `select`, `pyproject.toml:72`).
Separately, `_lazy_capture_if_missing` records its throttle marker (`:649`) **only** on the
`probe unavailable` branch — a *capture-time* failure (`:661`) falls to the outer `except: return`
(`:674`) and records/clears nothing.
**Risk if not fixed:** (U3) A subtly-broken loomweave degrades **invisibly** — the honesty invariant
keeps output correct (`NO_SNAPSHOT` / `attestation_incomplete`) but the **cause is lost**; an operator
cannot tell "loomweave absent" from "loomweave present but erroring." (U4) On a repo where loomweave
is reachable but capture consistently fails, **every** subsequent read re-pays the full probe spin-up
(~1–5 s) plus the failing capture, **forever, silently** — surfaces as "warpline got slow" with no
diagnostic trail.
**Effort:** S (the cheapest high-value items). Route the three swallows through
`store.log_health(repo, "<CODE>", repr(exc))` (the store handle is already in scope; this is the exact
pattern the federation seams already use in-band at `federation.py:248,279,315`); move
`_record_lazy_capture_attempt` into the **outer** `except`. Resolve the inert `# noqa` (add `BLE` to
`select` or drop the misleading comments).
**Dependencies:** None. **Bundled** under the *Acceptable Bundling* test: U4 is a reliability item, U3
is its observability *enabler* (F4 itself says "combine with F3's `log_health`") — genuine technical
overlap, reliability remains primary, no item diluted.

### 2d. U8 — Harden + test the loomweave stdio client (M, **Medium**)
**Evidence:** `LoomweaveMcpClient` (`loomweave.py:91-229`, ~170 LOC of `subprocess.Popen` +
`selectors` non-blocking I/O + deadline handling), with a bare `pass`-in-`except` (`loomweave.py:115`).
`test_loomweave_probe.py` exists but is not confirmed to exercise the concurrency/timeout paths.
**Risk if not fixed:** A deadlock / timeout / partial-read bug here degrades **every** graph-enriched
tool. A hung sibling could wedge a read path. This is the system's untested single-point reliability
risk.
**Effort:** M. Add a read **deadline** so a hung sibling cannot wedge a read; add focused tests for
partial reads, EOF/broken-pipe, oversized frames, and timeout.
**Dependencies:** None. Heaviest Phase 2 item (M effort + new tests) — schedule after the 2a–2c cheap
wins.

**Phase 2 Exit Criteria:**
- [ ] U2 — verification state aligns by **key**, not index (or a loud len/id-echo assertion guards it)
- [ ] U1 — `_assert_no_orphans` invariant + merge-family property test green; a deliberate orphan fails it
- [ ] U3 — the three read-path swallows emit a `health_log` breadcrumb; inert `# noqa` resolved
- [ ] U4 — throttle marker stamped on **all** capture-failure modes (verified by a capture-raises test)
- [ ] U8 — loomweave client has a read deadline + partial-read/EOF/timeout tests
- [ ] Full existing suite (~1:1, 59 files) green; `warpline reverify` + `wardline scan` gates green

---

## Phase 3: Architecture Debt — the two god-units (~1–2 weeks; sequence matters)

**Goal:** De-concentrate the two structural Highs so the *next* contributor can change persistence or
the reverify flow without a single-file blast radius. **Behavior-preserving by construction**, each
move gated by the existing test suite. These are below Phase 2 because they threaten the *next* edit,
not today's correctness. **Optional / opportunistic** if feature work isn't about to touch these files.

### 3a. U6 — Split `store.py` (1863-LOC god-module) along its four visible seams (L, **High/maintainability**)
**Evidence:** `store.py` holds DDL (`:35-107`), the migration runner + presence-floor (`:123-630`),
the read-only `read_store_binding` probe (`:306-402`), and the 40-method `WarplineStore` class
(`:633-1863`). fan_in 38, fan_out 0 internal (it is a true cohesive foundation — the split is a
navigation/merge-conflict-tax fix, not a coupling fix).
**Risk if not fixed:** Single-file blast radius + merge-conflict tax for every persistence edit;
the foundation stays hard to navigate as capability lands on top of it.
**Effort:** L (mechanical, behavior-preserving). Split into `store_schema.py` (SCHEMA + MIGRATIONS +
`_run_migrations` + `_schema_presence_floor`), `store_binding.py` (`read_store_binding` +
`StoreBinding`), `store_identity_merge.py` (the `reresolve_entity_key_sei` → `_merge_into_twin` →
`_repoint_*` family, `:770-1054`), and `store.py` (the `WarplineStore` read/write methods).
**Dependencies:** Do **before** 3b (the reverify extraction needs stable store seams). The
`store_identity_merge.py` unit **pairs with U1** (2b) — extract the merge family into the module whose
invariant Phase 2 just added.

### 3b. U5 + U7 — Extract `reverify_worklist` assembly into the S3 compute layer (L, **Medium-High**)
**Evidence:** `reverify_worklist` is 276 LOC, fan_out **34** (highest in the system,
`commands.py:793-1069`), orchestrating ≥8 concerns inline: ref resolution, lazy capture, blast,
per-entity verification-freshness (`_verif_cache` + `_covers`/`_between` closures, `:836-887`),
stale-first presort, SEI/locator capture (`:934-945`), federation merge (`:954-974`), attest
content-hashing (`:1002-1014`), impact-completeness, list pipeline, envelope assembly. The reusable
glue (`_lazy_capture_if_missing`, `_attest_content_hashes`, `_merge_federation_enrichment`,
`_member_scalar`, the verification cache) is **stranded in S4** (U7 / D4) when it belongs in S3.
**Risk if not fixed:** This is *where reliability bugs hide* — U2 (positional invariant) and U4
(throttle gap) both live in this function's orbit precisely because the concentration hides invariants.
The flow cannot be unit-tested below the integration level.
**Effort:** L. Extract a `VerificationResolver` (cache + `_covers`/`_between`), the SEI/locator capture,
and the stranded glue down into S3 / a `reverify_assembly.py` seam. Target: no tool body over ~80 LOC;
each extracted concern gains unit tests.
**Dependencies:** Do **after** 3a (stable store seams first). Also tidies the minor S2↔S3 lazy-import
back-edge (`store.py:1468-1469,1554`) the assessment's Focus-5 note flags.

**Phase 3 Exit Criteria:**
- [ ] `store.py` split into the four seam modules; all imports resolve; suite green
- [ ] `store_identity_merge.py` carries the U1 `_assert_no_orphans` invariant alongside the merge family
- [ ] `reverify_worklist` reduced to thin wiring (≤ ~80 LOC); verification + attest assembly unit-tested in S3
- [ ] Zero behavior change: golden vectors + honesty-invariant suite + contract schema tests unchanged and green
- [ ] `module_circular_import_list` still 0; the S2↔S3 lazy-import workaround removed or documented

---

## Phase 4: Performance (~1–2 days; opportunistic — attest path only)

**Goal:** Remove the one reasoned (not measured) performance hazard.

### 4a. U9 — Batch the attest loomweave round-trips (M, **Medium**, attest path only)
**Evidence:** `_attest_content_hashes` (`commands.py:678-709`, loop `:698-704`) issues one
`entity_resolve` loomweave subprocess JSON-RPC call **per SEI**; the docstring itself flags "batching
is a clean later optimization."
**Risk if not fixed:** A large worklist × subprocess-per-SEI is slow — but **only** when an
`attest_bundle` is supplied, so the blast radius is bounded and the cost is reasoned, not profiled.
**Effort:** M. Add a batch resolve to `LoomweaveMcpClient` (single round-trip for N locators); call it
once instead of per-SEI.
**Dependencies:** Cleanest **after** U8 (4a touches the same client U8 hardens) and after 3b (the
attest hashing moves in the assembly extraction). No urgency — schedule when next touching the attest
path or after a real profile confirms the cost.

**Phase 4 Exit Criteria:**
- [ ] `LoomweaveMcpClient` exposes a batch resolve; `_attest_content_hashes` calls it once
- [ ] Attest-path behavior unchanged (content-hash equality still mechanical); suite green

---

## Phase 5: Code Quality & Hygiene (~1–2 days total; opportunistic — do when touching the area)

**Goal:** Clear the Low-severity maintainability and hygiene items. Several are one-liners that should
**ride along** with adjacent Phase 2/3 work rather than be batched (flagged below).

| Item | Evidence | Risk if not fixed | Effort | Notes |
|------|----------|-------------------|--------|-------|
| **U11** — `_repoint_snapshot_edges` self-edge: docstring ≠ code | `store.py:999` (doc) vs `:1040-1054` (code); contrast `_repoint_co_change_pairs:946-948` | Spurious `twin→twin` row persists in `snapshot_edges` (benign today — BFS `seen`-set skips it, `propagation.py:81-83`); the doc/code mismatch is the maintenance trap U1 warns about | S (1 line) | **Ride along with 3a** (same merge family). Add `if new_source == new_target: continue` or fix the docstring. |
| **U16** — three declared-but-unraised `WarplineError` subclasses | `errors.py:76,124,130`; vocab assert `errors.py:52` | None — **almost certainly intentional** frozen-vocab pins (`warpline.error.v1`) | S | **Document as reserved; do NOT delete** (deleting is a contract change). Add a `# reserved frozen-vocab` annotation. |
| **U14** — git verbs lack `--` options terminator | `git.py:39-43,95,109-114,130` | Argument-injection residual (ref starting with `-`) on read-only verbs; outside the local-first threat model | S | Defense-in-depth. Insert `"--"` before ref/path args where the verb supports it. |
| **U13** — hardcoded `/tmp` + `spike/REPORT.md` defaults | `productization.py:7,20`, `cli.py:371`, `dogfood.py:24,79` | Non-portable (not Windows/multi-user-safe); internal tooling only | S | Derive from `tempfile.gettempdir()`; make the report path a config'd arg. |
| **U15** — `listing.py` FS overflow-spill in pure S1 layer | `listing.py` `apply_overflow`; `02-subsystem-catalog.md:54` | I/O leak into the purest layer; complicates isolated unit-testing | S | Inject the spill sink (writer callback) so predicates stay pure. |
| **U10** — per-surface input default/coercion duplication | `mcp.py:330-379` vs `cli.py:188-374`; defaults also in `commands.py` signatures | Defaults in **three** places drift silently; partly inherent to dual surfaces | M | Centralize defaults in one constant table both surfaces import; or add a CLI/MCP envelope-parity test. |
| **U12** — `dogfood.py` re-implements S5/S7 plumbing | `dogfood.py:525` (`_call_tool_stdio`), `:568` (`_git`) vs `git.py`, `mcp.dispatch` | Local copies can drift from shipped seams; acceptable for a harness | M | Reuse `git.py` + in-process `mcp.dispatch` where a fresh subprocess isn't required. |
| **U17** — 3 `test_attest.py` HighEntropyHex findings are **false positives** | content-addressing hashes + synthetic `bbbb…` fixture + a commit SHA as test data (verified); `.env` git-ignored | None (verified non-secrets) | trivial | **Waive in the loomweave/wardline baseline** (housekeeping, outside `src/`). |

**Phase 5 Exit Criteria:**
- [ ] U11 fixed (one line) — ideally folded into Phase 3a
- [ ] U16 annotated as reserved frozen-vocab (not deleted)
- [ ] U14 `--` terminator added to read-only git verbs
- [ ] U10/U12/U13/U15 addressed when next touching their modules (no forced batch)
- [ ] U17 false-positive secrets waived in the scanner baseline

---

## Stakeholder Concerns Addressed

The "stakeholder" here is the **product owner** (per the `docs/product/` ownership workspace). The
concerns are integrated honestly — none reprioritizes a higher risk class.

| Stakeholder | Concern | Resolution |
|-------------|---------|------------|
| Product owner | The product direction is the **capability ladder / north-star** (Rung 2/3, federation-enriched reverify), not maintainability. This roadmap moves a **guardrail**, not the north-star. | Acknowledged — stated up front. Phase 2 is **cheap (~1 week, mostly S/M)** and reduces future-edit hazard on `store.py`/`reverify_worklist` — the exact chokepoints every *future* capability bet must edit. It is hardening that *protects* the feature roadmap, sequenced not to block it. |
| Product owner | Don't let a refactor budget stall feature delivery. | Phase 3 (the L-effort god-unit splits) is explicitly **optional/opportunistic** — recommended *when the next feature is about to touch* `store.py`/`reverify_worklist`, not as a standalone stop-the-world refactor. Phases 1–2 deliver almost all the risk reduction. |
| Product owner | Open escalation: cut **1.3.0** vs **1.2.x** for the 37-commit `release/1.2.0` payload. | **None of this roadmap blocks the release** — 0 shipping defects. Phase 2 reliability items *could* optionally land in the next minor, but no item gates the cut. The release decision is independent of this roadmap. |
| Architecture analysis (handover §5) | Owner decision points: (1) adopt FKs or keep manual (U1)? (2) refactor budget for U5/U6? (3) bridge to the tracker? | (1) **Recommend keep-manual + add the invariant test** (U1/2b) — FKs would fire mid-merge and break the intentional SEI-orthogonal repoint. (2) Budget = Phase 2 now (~1 wk); Phase 3 deferred-until-touched. (3) Recommend promoting **U1, U2, U3, U4 as P1/P2** and **U5, U6, U8 as P2** to filigree, labelled `arch-analysis-2026-06-28` — but that is a **gated owner action** (see Next Steps), not auto-executed here. |

---

## Priority Adjustments

**Original Technical Assessment** (the handover's value×inverse-effort *wave* ordering):
- Wave 1 (cheap, high-leverage): U3+U4, U1, U2, U11+U14+U16, U17
- Wave 2 (structural): U6, U5+U7, U8
- Wave 3 (opportunistic): U9, U10, U12, U13, U15

**Adjusted After Risk-Hierarchy Discipline** (this roadmap):
- Phase 1 (Security): **NONE** — clean posture (vacuously satisfied)
- Phase 2 (Reliability & Correctness): U2, U1, U3+U4, **U8**
- Phase 3 (Architecture Debt): U6, then U5+U7
- Phase 4 (Performance): U9
- Phase 5 (Quality/Hygiene): U11, U16, U14, U13, U15, U10, U12, U17

**Changes Made:**
- **Pulled U8 forward** from the handover's Wave 2 into Phase 2 — it is a *reliability* item (a hung
  sibling degrades every graph tool), and risk class outranks the value×effort ordering that had it
  trailing the structural refactors.
- **Held U3 in the reliability phase despite its "code-quality/observability" category** — justified by
  genuine technical overlap with U4 (it is U4's observability enabler; the assessment itself pairs
  them), satisfying the *Acceptable Bundling* test. Reliability stays primary; nothing diluted.
- **Demoted the cheap hygiene one-liners (U11/U14/U16) out of "Wave 1" into Phase 5** by *priority*,
  while flagging that the trivial ones (esp. U11) should *ride along in execution* with adjacent
  Phase 2/3 work. Cheapness pulls them forward in *scheduling*, never in *risk priority*.
- **Did not bundle** anything across risk classes as a rationalization; the only bundle (U3+U4) is
  within one class with real overlap.

**Security Priority Maintained:** ✅
- No security item was deprioritized — none exists to deprioritize. The clean posture is
  evidence-cited (zero deps; no shell; parameterized SQL; argv-list). The one security-adjacent
  hardening nit (U14) was *identified and scheduled* (Phase 5), not silently dropped, and its
  Low severity — not stakeholder preference — placed it there.

---

## Next Steps (gated)

1. **Bridge to the tracker (owner-gated).** Recommended: promote U1/U2/U3/U4 (P1–P2) and U5/U6/U8 (P2)
   to **filigree** (warpline's own tracker — within the product grant), labelled
   `arch-analysis-2026-06-28`. **Not auto-executed** — the product session activated bet A
   (verification-freshness validation), not the hardening wave (bet C). Activating this roadmap is the
   owner's `DECIDE`.
2. **Per-refactor planning:** `axiom-planning:implementation-planning` for the Phase 3 structural moves
   (U5/U6) when activated.
3. **Run the gates** (`warpline reverify`, `wardline scan`, the full pytest suite) before/after each
   Phase 2/3 change — every item is behavior-preserving and must stay that way.

*Roadmap complete. Confidence: High (grounded in the directly-read file:line evidence of `05`/`06`/
`temp/debt-catalog.md`). The two structural Highs (U5/U6) and the silent-correctness Medium (U2) are
the items most worth an architect's attention; Phase 2 captures the bulk of the risk reduction in
~1 week.*
