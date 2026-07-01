# Warpline 5th-Producer Conformance — Hub Handover (FINALIZED, 2026-07-01)

Date: 2026-07-01
Status: **FINALIZED — ready to deliver to the federation hub owner.** Supersedes the
2026-06-29 and 2026-06-22 drafts. The DOCUMENT is complete; the two acts it asks for —
wiring warpline into the GS-7 oracle and freezing the glossary — are the owner's
outward-facing call (warpline's grant is repo-local). This package freezes nothing and
creates no hub or sibling work.

Producer: warpline (admitted 2026-06-13 as the federation's 5th member, PDR-0022).
**Branch of record: `main` @ `v1.3.0`** — released, annotated tag `v1.3.0` pushed to
origin (`3768794`; PDR-0010). The conformance package below is the shipped 1.3.0 surface.

## 0. State as of v1.3.0 (what a wiring engineer needs to know)

- **19 golden vectors**, all green (was 14 at admission; +5 through 1.3.0).
- **7 frozen MCP tools** (was 6; `warpline_verification_record` added — the 2nd mutating
  tool). The read-only `project_status` probe is an additive health surface, NOT a frozen
  data contract — exclude it from the frozen-inventory gate.
- **Four-member `include_federation` seam is fully LIVE** — filigree (work), wardline
  (risk + attest-2), legis (governance), plainweave (requirements). As of 2026-07-01 the
  plainweave producer is reshipped, so the requirements member is wired (not `disabled`).
- **The conformance manifest is current** — `reserved_shape_inbound` was refreshed
  (`18548ca`) to record wardline/legis as EARNED and plainweave as the 4th member, so the
  package already matches the committed consumer reality. No pre-wiring manifest edit needed.

## 1. What 5th-producer conformance is

Warpline contributes a golden-vector suite to the four-member GS-7 conformance oracle as
a fifth producer. Two artifacts:

- `tests/fixtures/contracts/warpline/golden-vectors.json` — the vector **manifest**
  (`schema: warpline.golden_vectors.v1`; `{id, seam, tool, assert}` objects + an
  `executable` descriptor + `reserved_shape_inbound`). Prose asserts, NOT a data-driven replay.
- `tests/contracts/test_golden_vectors.py` — the **executable**. Builds real-git fixtures
  + stubbed loomweave clients and calls `warpline.commands` / `warpline.snapshot` directly.
  The live assertions are here.

### Vector inventory (count: 19)

- Legacy (frozen 2026-06-13, 14): `GV-LW-1..5`, `GV-FI-1..3`, `GV-WL-1..3`, `GV-LG-1..3`.
- 1.2.0 hardening (4): `GV-LW-6` (atomic-capture fail-closed visibility),
  `GV-HON-SEI` / `GV-HON-GOV` / `GV-HON-REQ` (honesty triples for sei / governance /
  requirements absence).
- Verification-freshness (1): **`GV-VF-1`** — verification honesty on the reverify **data
  item** (never the frozen enrichment vocab): no source → every item `unverified` +
  `disabled` triple + `local_source_configured: false`; a recorded gate pass at the change
  commit → `fresh` + `last_verified_commit`; the worklist re-sorts stale-first but is
  **never filtered** (advisory, never gates).

### The frozen envelope / error contract (unchanged — additions are vN+1 URIs)

- **Success envelope** (`warpline.<contract>.v1`): `{schema, ok, query, data, warnings,
  next_actions, enrichment, meta}`. `meta.local_only` always `true`; `meta.peer_side_effects`
  always `[]`.
- **Enrichment vocab** (CLOSED, 6 keys): `sei` / `work` / `risk` / `governance` /
  `requirements` ∈ {present, absent, unavailable}; `edges` ∈ {present, absent, stale,
  partial, skipped, unavailable}. `requirements` is now a real (plainweave) consumer; the
  vocab is unchanged. Verification-freshness rides as a **reverify-item field**, deliberately
  NOT a 7th enrichment key — the frozen vocab is untouched.
- **Weft-reason triple** (`{reason_class, cause, fix}`): 11 classes — `clean`, `disabled`,
  `unresolved_input`, `rejected`, `dead_path`, `unreachable`, `misrouted`, `error`,
  `scheme_mismatch`, `stale`, `partial`. `clean` omits cause/fix; every other class carries both.
- **Error contract** (`warpline.error.v1`): 11 closed codes; 3 retryability values
  (`retry_safe`, `retry_with_changes`, `fatal`). Additions are a v2 URI, never a v1 mutation.

### Endorsed MCP names + shims (7 pairs)

| Endorsed name | Shim | Data schema | Mutates |
|---|---|---|---|
| `warpline_impact_radius_get` | `blast_radius` | `warpline.impact_radius.v1` | no |
| `warpline_edge_snapshot_capture` | `capture_snapshot` | `warpline.edge_snapshot.v1` | **yes** |
| `warpline_change_list` | `changed` | `warpline.change_list.v1` | no |
| `warpline_entity_churn_count_get` | `churn` | `warpline.entity_churn_count.v1` | no |
| `warpline_reverify_worklist_get` | `reverify` | `warpline.reverify_worklist.v1` | no |
| `warpline_entity_timeline_get` | `timeline` | `warpline.entity_timeline.v1` | no |
| `warpline_verification_record` | `verify-record` | `warpline.verification_record.v1` | **yes** |

Both mutating tools write only `.weft/warpline/`; all tools `local_only: true`,
`peer_side_effects: []`. Inventory source of record:
`tests/fixtures/contracts/warpline/mcp-tool-inventory.json` (`status: admitted-frozen`).

### Consumed sibling contracts (warpline mirrors; the producer owns each)

Inbound contracts warpline reads **enrich-only** and **echo-only** (never mints a verdict).
Note the two wiring modes — this is the one detail the 2026-06-29 draft stated imprecisely:

- **wardline** — **AUTO-WIRED** (not capability-gated): `WardlineDossierClient` over
  `wardline dossier` feeds the `risk` enrichment dimension on every `include_federation`
  run (degrades to `unreachable`/`disabled` if wardline is absent). Separately, the
  **attest-2** risk-as-verification path is opt-in via `--attest-bundle` (a PUSHED untrusted
  bundle; mechanical `(commit, content_hash)` equality, signature NOT verified). GV-WL-1..3
  pin the honesty.
- **legis** — **CAPABILITY-GATED auto-wire**: `LegisGovernanceClient` over
  `legis governance-read` (`governance_read.v1`) wires only when the installed legis
  advertises the verb; else honestly `disabled`. Mirrored byte-for-byte at
  `contracts/governance_read.v1.schema.json`; golden `legis-governance-read.golden.json`.
- **plainweave** — **CAPABILITY-GATED auto-wire** (the 4th member): `PlainweaveRequirementsClient`
  over `plainweave requirements-enrichment` (`weft.plainweave.requirements_enrichment.v1`)
  feeds the `requirements` dimension. **LIVE as of 2026-07-01** — the plainweave producer is
  reshipped and `PlainweaveRequirementsClient.available()` returns True. Goldens
  `requirements-enrichment.golden.json` (structure) + `requirements-enrichment.cli-envelope.golden.json`
  (byte-pinned CLI envelope).

## 2. How to wire it into GS-7 CI

- **Fixtures:** mount `golden-vectors.json` + `mcp-tool-inventory.json` into the oracle
  fixture tree (both portable — relocatable `executable` descriptor, cwd-independent fixture
  root). The three consumed-contract goldens (legis/wardline/plainweave) are additional
  fixtures the oracle MAY pin if it wants to gate consumer-mirror drift (owner's call, §5).
- **Executable entry point:** `tests/contracts/test_golden_vectors.py` — a pytest module,
  NOT a JSON replay. Run with the `warpline` package importable (manifest
  `executable.import_requires: warpline`) and `git` on PATH; it builds its own fixtures.
- **Producer registration:** key on `producer: "warpline"`, schema `warpline.golden_vectors.v1`,
  the `executable` descriptor, and the `vectors[]` index. Green = all 19 vectors pass.

## 3. OD-5 (RESOLVED-direction; wiring pending)

OD-5 is not an open adjudication — the interface-lock §8 records it resolved at lock time
(owner nod 2026-06-13): **fold warpline's golden vectors into the existing four-member GS-7
oracle as a fifth producer (one oracle, one gate, C-12).** The owner's remaining action is
the launch-runbook *wiring* (register warpline as the 5th producer, turn the gate on), not
the decision. Source: `weft/pm/2026-06-13-warpline-interface-lock.md` §8.

## 4. Glossary-freeze checklist (attestation on the owner's signal)

Already named non-draft — an ATTESTATION list, not pending renames:

- [ ] **MCP names** — the 7 endorsed names + 7 shims (§1) frozen as the public surface.
- [ ] **Error codes** — 11 codes + 3 retryability values under `warpline.error.v1`.
- [ ] **Enrichment vocab** — 6 closed keys + value sets and the 11 reason classes.
- [ ] **Schema URIs** — `warpline.golden_vectors.v1`, `warpline.mcp_tool_inventory.v1`,
  `warpline.error.v1`, `warpline.verification_record.v1`, and the 6 `warpline.<contract>.v1`
  data schemas frozen; any change is a new vN+1 URI.

## 5. Status (2026-07-01) — what's done, what's left for the owner

**Local conformance: PROVEN** on `main` @ `v1.3.0` — 19 golden vectors green; conformance
suite green (`test_golden_vectors.py` + `test_reason_vocab_conformance.py`); full warpline
suite 572 passed / 1 skipped. (Run the suite for the authoritative count.)

**Sibling consumption — all EARNED/LIVE (manifest already refreshed to match):**
- **loomweave** — PROVEN + FROZEN (`entity_resolve`, `entity_neighborhood_get`).
- **filigree** — EARNED (`entity_association_list_by_entity` + `issue_get`; GV-FI-1/3).
- **wardline** — EARNED (auto-wired `dossier` → `risk`; + the attest-2 path).
- **legis** — EARNED (capability-gated `governance_read.v1`).
- **plainweave** — LIVE (capability-gated `requirements_enrichment.v1`; producer reshipped 2026-07-01).

**Remaining — the owner's outward-facing acts (NOT warpline-autonomous, NOT done here):**
1. **Wire warpline into the GS-7 oracle** as the 5th producer and turn the gate on (§2) —
   the launch-runbook step OD-5 resolved the direction for.
2. **Sign the glossary-freeze attestation** (§4).
3. **Decide** whether the 3 consumed-contract goldens (legis/wardline/plainweave) join the
   GS-7 fixture set or stay warpline-local mirror tests (§2).

*Done since the 2026-06-29 draft (no longer owner action items): the manifest
`reserved_shape_inbound` refresh (`18548ca`), and the plainweave producer reship that made
the requirements member live.*
