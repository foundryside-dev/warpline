# Technical Debt Catalog — `warpline` (`src/warpline/`)

**Scope:** `src/warpline/` only — 30 `.py` files, ~10,411 LOC,
flat package, zero runtime deps, Python 3.12, `mypy --strict`, `ruff`. `tests/` and the
sibling `heddle.*` repo are **out of scope** and excluded from every row below.

**Source basis:** subsystem catalog `../02-subsystem-catalog.md`; full read of
`commands.py` and `store.py:1–1342`; targeted reads of `store.py` merge family
(770–1045) and schema DDL (37–230); grep sweeps for fail-soft swallows, hardcoded
paths, batching markers, arg-coercion; loomweave `entity_dead_list` / `entity_todo_list`.

**Headline:** this is a **disciplined, healthy codebase** — zero deps, `mypy --strict`,
`ruff`, no circular imports, **no TODO/FIXME/HACK/XXX markers anywhere in src**, correct
forward-only migration + `BEGIN IMMEDIATE`/rollback transaction discipline, honest
fail-soft degradation as first-class return values. The debt below is overwhelmingly
**Med/Low structural-cohesion and observability** debt, with a **single High** (data
integrity). The catalog is deliberately not inflated; see Confidence/Caveats.

---

## Debt Inventory

| ID | Item | Location (file:line) | Category | Severity | Effort | Remediation |
|----|------|----------------------|----------|----------|--------|-------------|
| D1 | `store.py` god-module: one 1863-LOC file holds schema DDL, the migration runner, `_schema_presence_floor`, the read-only `read_store_binding` probe, **and** the 40-method `WarplineStore` data-access class. | `store.py:37–230` (DDL/migrations), `store.py:306` (`read_store_binding`), `store.py:469` (`_schema_presence_floor`), `store.py:633–1863` (`WarplineStore`) | god-module | Med | L | Split package: `store/schema.py` (SCHEMA + migrations + presence-floor), `store/binding.py` (`read_store_binding`/`StoreBinding`), `store/identity.py` (the reresolve/merge family), `store/store.py` (the read/write methods). Pure mechanical extraction; no behavior change. |
| D2 | FK-less derived tables — referential integrity maintained **only** by hand in the identity-merge path. `co_change_pairs` has **no** FK to `entity_keys`; `snapshot_edges` has an FK on `snapshot_id` but **none** on `source_entity_key_id`/`target_entity_key_id`. A future edit to the ~270-LOC merge family can silently orphan rows — `PRAGMA foreign_keys=ON` (store.py:652) gives no backstop on those columns. | tables: `store.py:91` (`snapshot_edges`), `store.py:184` (`co_change_pairs`); manual integrity: `reresolve_entity_key_sei` `store.py:770–829`, `_merge_into_twin` `store.py:831–902`, `_repoint_co_change_pairs` `store.py:903–991`, `_repoint_snapshot_edges` `store.py:992–1045` | coupling (data-integrity) | **High** | M | Keep the SEI-orthogonal design (deliberate per `store.py:177`) — do **not** naively add FKs/CASCADE that would fire mid-merge. Instead add a **post-merge referential-integrity invariant**: a `_assert_no_orphans` check (debug/CI) + a property test that runs the full merge against a fixture and asserts every `*_entity_key_id` resolves. Turns a silent-corruption risk into a loud test failure. |
| D3 | `reverify_worklist` complexity hotspot — 276 LOC, fan_out 34, orchestrates ≥8 concerns in one body: ref resolution, lazy capture, blast, per-entity verification-freshness (inline `_verif_cache` + two git-reachability closures `_covers`/`_between`), federation enrichment merge, attest content-hashing, impact-completeness, the list pipeline, and envelope assembly. Hard to unit-test below integration level. | `commands.py:793–1069`; verification assembly `commands.py:836–887`; attest/sei collection `commands.py:927–1014` | complexity | Med | L | Extract the verification-freshness assembly (`changes_by_key` build, `_covers`/`_between`, `_verif_cache`, `verification_for`) into S3 (`verification.py` or a new `reverify_assembly.py`); extract the affected-SEI/locator collection + attest hashing. Leave `reverify_worklist` as thin wiring. Unlocks unit tests for each concern. |
| D4 | Orchestration glue stranded in S4 `commands.py` that arguably belongs in the S3 compute layer / a seam-assembly module — reusable-looking helpers living in the command module. | `_lazy_capture_if_missing` `commands.py:615–675`, `_attest_content_hashes` `commands.py:678–709`, `_member_scalar` `commands.py:1091–1110`, `_merge_federation_enrichment` `commands.py:1112–1154`, inline verification cache `commands.py:873–887` | coupling (layering) | Med | M | Move these down into S3 / a dedicated assembly seam so `commands.py` is pure wiring (`resolve → open store → compute → list → envelope`). Improves testability and keeps the layer boundary the subsystem catalog documents. |
| D5 | N+1 sibling round-trips in `_attest_content_hashes` — one `entity_resolve` loomweave subprocess JSON-RPC call **per SEI** in a loop; the docstring itself flags "batching is a clean later optimization". Only paid when an `attest_bundle` is supplied, but a large worklist × subprocess-per-SEI is slow. | `commands.py:678–709` (loop `698–704`; admission `commands.py:690`) | perf | Med | M | Add a batch resolve to `LoomweaveMcpClient` (single round-trip for N locators) and call it once here instead of per-SEI. Bounded blast radius (attest path only), so schedule after the structural items. |
| D6 | Silent fail-soft swallows with **no observability breadcrumb** — broad `except Exception` that returns a degraded value with no log/metric/warning emitted, so a persistently-failing dependency degrades invisibly. The `# noqa: BLE001` annotations are **inert** (BLE is not in `ruff` `select=["E","F","I","UP","B"]`, pyproject `72`). | `session_context` `commands.py:77`, `_lazy_capture_if_missing` `commands.py:674`, `_attest_content_hashes` `commands.py:707`; sibling-probe swallows `loomweave.py:115,262,315`, `siblings.py:54,65` | observability | Med | S | On each swallow path emit a structured breadcrumb (a `health_log` row, stderr diagnostic, or an envelope `warning`) so silent degradation is detectable in the field. Narrow the `except` to the expected transport/IO classes where feasible. Cheapest high-value item. |
| D7 | `dogfood.py` re-implements git + tool-call plumbing locally — `_git` and `_call_tool_stdio` duplicate S5 (`git.py` reachability/run helpers) and S7 (`mcp.dispatch`). 575-LOC harness; the local copies can drift from the shipped seams. | `_call_tool_stdio` `dogfood.py:525`, `_git` `dogfood.py:568` (vs `git.py`, `mcp.dispatch`) | duplication | Low | M | Reuse `git.py` primitives and call `mcp.dispatch` in-process where the harness doesn't specifically need a fresh subprocess. Acceptable for a test harness, but note the drift risk if kept. |
| D8 | Hardcoded non-portable default paths in lifecycle tooling — `/tmp/...` (not Windows-portable, not multi-user-safe) and a fixed `spike/REPORT.md` report location baked into defaults. | `productization.py:7` (`/tmp/...results.json`), `productization.py:20` & `cli.py:371` (`spike/REPORT.md`), `dogfood.py:24` (`/tmp/...results.json`), `dogfood.py:79` (`/tmp/...work`) | coupling (config/portability) | Low | S | Derive temp defaults from `tempfile.gettempdir()`; make the report path a required/config'd argument rather than a baked default. Internal tooling, so Low. |
| D9 | Argument-coercion duplicated across the two surfaces — `mcp.py` hand-rolls `_*_arg` coercion/validation while `cli.py` re-expresses the same via argparse `type=`. Two places to keep in sync for repo/depth/limit/key-ids. | `mcp.py:330–379` (`_repo_arg`/`_entity_ref_arg`/`_depth_arg`/`_key_ids_arg`/`_limit_arg`) vs `cli.py:188–374` (`type=Path/int` per subcommand) | duplication | Low | M | Centralize coercion+validation in one shared module both surfaces call. Partly inherent to dual surfaces (argparse vs JSON-RPC), so Low priority. |
| D10 | Declared-but-unraised error subclasses — three `WarplineError` subclasses are defined but **never raised** anywhere in `src/` or `tests/`. | `errors.py:76` (`InvalidRepoError`), `errors.py:124` (`PeerUnavailableError`), `errors.py:130` (`SnapshotUnavailableError`) | dead-code | Low | S | Either raise them at the conditions they name, or annotate as **reserved frozen-vocab error codes** (`warpline.error.v1`). **Caveat: very likely intentional contract surface** — these subclasses pin entries of the frozen error vocabulary (`errors.py:52` asserts code membership). Confirm intent before removing; default to documenting, not deleting. |
| D11 | I/O leak into an otherwise-pure S1 contract module — `apply_overflow` writes an overflow-spill file from inside `listing.py`, which is otherwise pure filter/sort/page predicates. | `listing.py` (`apply_overflow`, 437-LOC module; concern per `../02-subsystem-catalog.md:54`) | coupling | Low | S | Inject the spill sink (a writer callback) so `listing` stays pure and the FS write moves to the caller/seam. Minor. |
| D12 | Test-gap / fragility — the hand-rolled `selectors`-based stdio JSON-RPC client (`LoomweaveMcpClient`, ~170 LOC) is non-trivial concurrency/IO; a deadlock/timeout/partial-read bug here degrades **every** graph-enriched tool. Includes a bare `pass`-in-`except` (`loomweave.py:115`). | `loomweave.py` (`LoomweaveMcpClient`; bare `except` `loomweave.py:115`) | test-gap | Med | M | Add focused tests for partial reads, EOF/broken-pipe, oversized frames, and timeout; add a read-deadline so a hung sibling can't wedge a read path. (Confidence Medium — characterized via subsystem catalog + grep, not a full line-by-line read.) |

---

## Prioritized Top 5

1. **D2 — FK-less derived tables (High / M).** The only correctness-class item: a future merge-path edit can silently corrupt referential integrity with no DB backstop. Cheapest durable fix is a post-merge invariant + property test, not a schema rewrite. Do first.
2. **D6 — Silent fail-soft observability (Med / S).** Highest leverage-per-effort: small change, removes a whole class of invisible field degradation, and corrects the inert-`noqa` misconception. Quick win.
3. **D3 — `reverify_worklist` complexity (Med / L).** The system's complexity hotspot; extracting the verification + attest assembly into S3 unlocks unit testing of the most intricate flow and shrinks the widest function.
4. **D1 — `store.py` god-module split (Med / L).** Mechanical, behavior-preserving package split that makes the foundation tractable and pairs naturally with isolating the D2 merge family into its own module.
5. **D12 — Loomweave stdio client test-gap (Med / M).** Risk mitigation for a single point whose failure degrades every graph-enriched tool; add timeout + partial-read/EOF tests before this bites in the field.

---

## Confidence Assessment

- **Overall: High** for D1–D6, D8–D11 (direct file:line evidence, most from full reads of `commands.py` and `store.py:1–1342`, plus DDL and merge-family reads).
- **Medium** for D7 and D12 (characterized via the subsystem catalog + grep + signatures, not a full line-by-line read of `dogfood.py`/`loomweave.py`).
- **The "healthy codebase" assessment is itself a finding, not a gap:** zero deps, `mypy --strict`, `ruff`, no circular imports, no TODO/FIXME markers (confirmed by both `grep` and loomweave `entity_todo_list`), correct migration/transaction discipline. Severity was deliberately held down to avoid inflation.

## Risk Assessment

- **D2 is the only item with a correctness/data-loss failure mode** (silent referential-integrity corruption on a future merge edit). All others are maintainability, performance-under-load, observability, or hygiene — none can produce a wrong answer to a user today.
- **Severity-inflation risk** was the primary cataloging risk and was actively resisted; if anything these severities are conservative.
- Acting on D1/D3/D4 (structural moves) carries normal refactor risk — gate each behind the existing test suite; they are behavior-preserving by construction.

## Information Gaps

- `dogfood.py` (575 LOC) and `loomweave.py` (433 LOC) were **not** read line-by-line — D7/D12 rest on the subsystem catalog, grep, and signatures. A full read could refine effort or surface sub-items.
- `cli.py`, `mcp.py`, `federation.py`, `install_support.py` were covered via grep + docstrings + the `commands.py` contract they call, not full reads — D9 duplication is confirmed at the helper level but the exhaustive coercion-divergence list was not enumerated.
- No runtime profiling was done; **D5's perf impact is reasoned (subprocess-per-SEI), not measured.**
- Cyclomatic-complexity and fan-out figures for D3 are taken from the subsystem catalog, not independently recomputed.

## Caveats

- **D10 is almost certainly intentional**, not a defect — the three unraised error classes pin entries of the frozen `warpline.error.v1` vocabulary. Listed for completeness; the remediation is "document as reserved," not "delete."
- **D2's framing is "accepted tradeoff with fragility risk," not "they forgot FKs"** — the SEI-orthogonality is deliberate (`store.py:177`) and the `_repoint_*` family exists *because* manual integrity was chosen over CASCADE.
- The loomweave `entity_dead_list` was **not** used as evidence beyond D10: it is dominated by false positives — Protocol ports (`ToolClient`/`WorkClient`/`RiskClient`/`LegisClient`/`NeighborhoodClient`, referenced via type annotations not call edges), `WarplineStore` (instantiated via the `.open()` classmethod), `tests.*` (out of scope), and `heddle.*` (a **different repo**). Those are not debt.
- `store.py`'s `except BaseException: ROLLBACK; raise` handlers (`627`, `827`, `1814`) are **correct transaction discipline**, not fail-soft swallows — deliberately excluded from D6.
- `warpline_entity_key_id` was investigated as a possible advertise-and-ignore input and **cleared**: it is genuinely handled with degradation in `store.resolve_ref` (`store.py:1331–1338`).
