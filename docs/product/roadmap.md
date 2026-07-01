# Roadmap - Warpline

Updated: 2026-07-01 (PDR-0011 — the 5th-producer conformance handover was **DELIVERED to the weft hub**; warpline's OD-5 obligation is discharged [GS-7 wiring + glossary freeze are now the hub's]. v1.3.0 released [PDR-0010]. Near-term intent → **Rung 3 (predictive)**)

Sequencing, WSJF / cost-of-delay, and dated forecasts are produced by
program-management. This file records bets as intent, not a delivery schedule.
Do not compute WSJF here; hand the committed bet over for sequencing.

## The capability ladder (the directional backbone)

Warpline's value comes from the one thing no other federation member can hold:
**cross-run history keyed on a stable identity (SEI).** Loomweave is amnesiac by
design (it owns *now*); Warpline is the only member that can *remember*. The
ladder below is how that monopoly compounds — each rung enriches the per-entity
**temporal dossier** an agent reaches by SEI before it claims "done." Every rung
stays advisory, enrich-only, and honest (`cause + reason_class + fix`); none of
them ever gate.

> The near-term stabilization gaps and the long-horizon vision are the *same
> road*. Rungs are capability tiers, not a delivery schedule — see Now/Next/Later
> for horizon intent.

### Rung 0 — Modularity foundation *(hygiene; unblocks the rest)*

- **Split `commands.py`** (959 LOC; Loomweave emits a weak-modularity finding and
  pyright's reference-resolution times out on it). All six tool bodies live in
  this one module, so it is the chokepoint every later rung edits. Behaviour-
  preserving decomposition into a cohesive command package (per-tool / per-seam
  modules) before new capability lands on top of it.

### Rung 1 — Descriptive, made complete & self-healing *(stabilize the spine)*

- **Self-healing SEI re-resolution.** SEI is resolved at ingest only, so any event
  ingested while Loomweave was unreachable is stored `sei: null` *permanently* —
  silently degrading every join to the fragile `locator`. Add a re-resolution
  sweep that re-keys `sei: null` change-events whenever Loomweave is reachable.
  The spine is only worth what fraction of it is joinable.
- **Auto edge-snapshot capture.** The post-commit hook ingests change events but
  never captures a snapshot, so `impact_radius` / `reverify` return `NO_SNAPSHOT`
  by default. Wire capture (or lazy on-demand capture) into the ingest path so the
  headline reads are non-empty in normal use.
- **Honesty completion.** Every enrichment dimension carries `cause + reason_class
  + fix` (the `weft-reason` contract) so an inert seam reads as inert, never as a
  true-negative. (G1 in flight.)

### Rung 2 — Diagnostic *(behaviour over time — capabilities only Warpline can own)*

- **Temporal coupling / co-change graph (SEI-keyed).** "These entities change
  together 84% of the time — with *no* call edge between them." Structural
  analysis physically cannot see this. Powers the completeness check no other tool
  can make: *"you touched X; history says Y moves with it 9/10 times and you
  didn't."*
- **Verification freshness — staleness-of-trust.** Track `last_verified` (CI green,
  test pass, Legis attestation, Filigree closure), not just `last_changed`.
  Reverify shifts from "changed since HEAD~1" to *"changed since last proven-good,"*
  with a trust-decay signal.
- **Light up the flagship's inert dimensions — DONE (all four members live).** The
  reverify worklist's `include_federation` seam once had only work (Filigree) live; the
  other dimensions rode reserved. Now all four federation members are real consumers:
  work (Filigree), risk (Wardline, via the attest-2 / `governance_read.v1`-adjacent
  consumers — committed on `release/1.2.0`), governance (Legis, `governance_read.v1` —
  committed), and **requirements (Plainweave, `weft.plainweave.requirements_enrichment.v1`
  — PDR-0008, built+accepted, uncommitted on `release/1.2.0`)**. Each is advisory,
  honest (`cause + reason_class + fix`), never gates, and never collapses
  `unavailable`→`absent`. RESERVED-SHAPE consumption is now proven for every member; the
  remaining step is the `release/1.2.0` version cut (owner escalation).

### Rung 3 — Predictive *(forecast — the "throw tokens at it" tier)*

- **Empirical blast radius.** Static blast radius says what *could* be affected;
  Warpline learns what *was* — when X changed historically, which Wardline finding
  appeared, which Filigree issue reopened, which test went red, which attestation
  failed. Yields a historical regression rate per entity.
- **Preflight prediction.** Co-change graph + causality run *forward*: "if you
  touch X, history predicts you'll also touch {Y, Z} and must re-verify {A, B},
  ~N% confidence."
- **Risk trajectory.** Fuse churn × findings-over-time × fan-in into a *time-aware*
  hotspot score with a slope: "highest-risk entity this quarter, and getting
  worse."

### Rung 4 — The temporal fabric *(super-future)*

- **Time-travel / counterfactual queries.** Reconstruct the full impact graph as of
  any commit — replay for architecture.
- **Ownership & abandonment over time.** Churn velocity per maintainer, bus-factor
  drift, agent-only-churn detection.
- **Fleet-wide temporal impact.** Federate temporal facts across the suite —
  "this SEI's change in repo A historically precedes breakage in repo B" (the
  PDR-0024 fleet frame). Must not violate the no-shared-store anti-goal: federate
  by SEI join at read time, never a central mirror.
- **Semantic change typing.** Classify change kind (signature / behaviour /
  refactor-only / doc-only) so reverify is proportionate to the risk of the change.

## Temporal correlation spine *(cross-cutting — enables Rung 3)*

The SHA *is* the timeframe. A code change happens inside a working context
(`branch@sha` at the moment warpline detects it); the sibling "meta-changes"
attached to that change — an issue that moved in Filigree, a finding that appeared
in Wardline, an attestation in Legis, a graph delta in Loomweave — share that same
git anchor. If every event carries the anchor, the full bundle reconstructs by a
read-time join, with **no member mirroring another's data and no new minted
identifier** (git already owns the key — enrich-only by construction). This is the
mechanism that turns Rung 3's "what actually broke when X changed" from fuzzy
temporal correlation into a trivial join.

- **Warpline-local capture *(within repo autonomy)*.** The store records the
  *introducing* commit (`change_events.commit_sha`) but has **no `branch`** and no
  **detection/working-context** anchor distinct from it. Capture `branch + HEAD
  SHA + detection timestamp` as the working-context anchor on each detected change.
  A fact about warpline's own observation; imposes nothing on siblings.
- **Federation correlation contract *(RATIFIED — PDR-0025, 2026-06-16)*.** The
  foundation **sponsored the contract in full**: warpline owns the
  **temporal-episode axis** (a domain extension, *not* a second identity authority;
  orthogonal to SEI). The no-broker line is owner-confirmed (enrich-only metadata +
  decentralized read-time join). **Steps 1–2 (local capture + reconstruction demo)
  are authorized as warpline autonomy under the ratified contract**; the demo is now
  a *validation/shaping* gate, not go/no-go. The cross-member "stamp the originating
  `branch@sha`" convention is still **hub-authored and adopted incrementally** — no
  sibling obligation (Filigree/Wardline/Legis/Loomweave) freezes until the hub
  authors it against warpline's demonstrated reconstruction. Enrich-only throughout.
- **PM conditions (PDR-0025 — load-bearing):**
  - **Squash-merge is the headline failure, not an edge case.** Squash/rebase
    *rewrite* SHAs, orphaning every stamped anchor when a PR merges. This is distinct
    from a *rename* (PDR-0021; the rename feed carries no rewrite reconciliation).
    The demo MUST run on a real squash-merge fixture. Candidate to test (not
    prescribed): a **Legis merge-mapping** `{squashed-away SHAs} → {new mainline
    SHA}` (Legis observes the merge) — vs. surviving on `branch` + episode-boundary
    alone.
  - **Episode boundary ≈ work-session** (the desk/employee model), not per-commit;
    with an honest `weft-reason` fallback for dirty-tree / detached-HEAD.
  - **Sequencing fence:** Rung-3 / token-tier; sits *behind* the four-member launch
    cutover (`weft-4b2f948f70`) and warpline's base-impl fast-follow.

## Temporal common operating picture *(the consumer surface of the spine)*

The spine is plumbing; the **temporal COP** is the product. As the federation's
temporal authority, warpline's headline job becomes: *given a frame — an edit, a
rev range, a time window, a `branch@sha`, or a SEI — return the assembled
cross-member picture, "within this range, here's what everyone tells me they
changed."* Code changes (warpline-owned), work-state moves (Filigree), findings
(Wardline), attestations (Legis), graph deltas (Loomweave) — **each fact
attributed to its owning member, composed at read time, never mirrored.**

- **Mechanism:** the `include_federation` consult (`federation.py`) *generalized* —
  from "enrich the reverify worklist" to "assemble the full temporal picture over a
  range." The read surface is warpline-local (autonomy); its richness scales with
  stamping adoption (enrich-only ramp — useful on whoever is reachable today,
  fuller as the convention lands).
- **Coverage is part of the picture (non-negotiable honesty).** The COP always
  renders *who answered, who was unreachable, and how stale* (`cause + reason_class
  + fix` per source). A COP with a dark sector that *looks* empty is worse than no
  COP — an unmonitored frame must never read as "nothing changed."

## Now (committed)

The Rung-2 diagnostic tier is complete and **shipped as v1.3.0** (PDR-0010); the
**5th-producer conformance handover is delivered to the hub** (PDR-0011 — warpline's OD-5
obligation discharged). Near-term intent → **Rung 3 (predictive)**; the GS-7 oracle wiring +
glossary freeze are now the hub's to execute, not warpline's.

- **Rung 2 — verification-freshness** — *DONE* (PDR-0005 → accepted PDR-0007). The
  `last_verified` trust-decay axis, merged and validated on a real repo against its
  reversal trigger.
- **Rung 2 — light up the inert dimensions** — *DONE* (PDR-0008). All four
  `include_federation` members are real reverify consumers: filigree (work), wardline
  (risk / attest-2), legis (governance), plainweave (requirements) — the dimension
  warpline had never wired.
- **Reliability hardening (arch-analysis Phase 2)** — *DONE* (PDR-0009). U1/U2/U3/U4/U8:
  the FK-less referential-integrity invariant, the order-drift identity echo, read-path
  observability, the throttle gap, and loomweave-client hardening. Guardrail work that
  de-risks the `store.py` / `reverify_worklist` chokepoints every future bet must edit.
- **v1.3.0 — SHIPPED** (PDR-0010, owner-directed). The four-member-federation +
  verification-freshness + Phase-2 stack merged to `main` (`3768794`), tagged `v1.3.0`,
  pushed to origin, and installed into the live MCP tool. Retires the release escalation.
  *Post-release gap:* the `requirements` member reads `disabled` until the plainweave
  producer binary is reshipped (PDR-0008 watch).
- **Evidence freshness** — keep dogfood, productization, lint/type/test, and
  member-diff gates aligned as Warpline evolves.

> **Spine hardening — SHIPPED in v1.2.0** (PDR-0004 accepted; PDR-0006 accept+ship
> after a release-grade review). Capture is correct-by-construction (atomic,
> fail-closed-locked), honesty is complete (every dimension carries the
> `cause + reason_class + fix` triple), and the 5th-producer conformance package
> exists. No longer in-flight. The remaining **hub-handover delivery** is an owner
> escalation (tracked in `current-state.md`); review follow-ups are tracked issues
> warpline-d7d04243b2 / -fc09bdeddd / -d88e223731 / -17242c627b.

## Next (shaped, decreasing certainty)

- **Rung 2 — sibling-sourced verification** — wardline-resolved / filigree-closed /
  legis-attested as `last_verified` sources, once those sibling surfaces exist (each
  an owner/sibling escalation; honest-absent until then).
- **Federation conformance oracle inclusion — warpline-side DELIVERED (PDR-0011).**
  warpline's 19 golden vectors + the finalized handover were delivered to the weft hub; the
  GS-7 oracle wiring + glossary freeze are now the **hub's** to execute (OD-5 resolved-direction).
  No longer a warpline obligation — reopens only if the hub returns the package for changes.

## Later (directional bets, no order, no dates)

- **Rung 3 — predictive** — empirical blast radius, preflight prediction, and
  time-aware risk-trajectory scoring.
- **Rung 4 — temporal fabric** — counterfactual graph reconstruction, ownership
  drift, fleet-wide temporal impact, and semantic change typing.
- **Rename and lineage continuity** — settle the C′/A′ locator-rename source once a
  proven need exists; largely subsumed by Rung 1 re-resolution (re-resolving to the
  current SEI makes renames Loomweave's problem, already solved).
