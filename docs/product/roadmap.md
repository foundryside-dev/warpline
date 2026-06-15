# Roadmap - Warpline

Updated: 2026-06-15 (PDR-0002 — the capability ladder)

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
- **Light up the flagship's inert dimensions.** The reverify worklist freezes four
  enrichment slots; only work (Filigree, SEAM 2) is live. Implement SEAM 3 (Wardline
  risk-by-SEI) and SEAM 4 (Legis governance/provenance) inbound reads so the
  worklist sorts by risk/governance, not just depth. (Both RESERVED-SHAPE — proving
  consumption is what freezes them.)

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

## Now (committed, in-flight)

- **Post-admission seam fast-follow** — Warpline was admitted as the 5th member
  (owner, PDR-0022, 2026-06-14); seam *contracts* are frozen, consumer
  *implementations* are an admitted fast-follow outside the launch cutover. The
  PDR-0023 honesty work is landing (`weft-reason` G1, list-ergonomics G2, the
  `include_federation` hub-blessed consult).
- **Rung 0 — `commands.py` refactor** — modularity foundation; behaviour-preserving.
- **Evidence freshness** — keep dogfood, productization, lint/type/test, and
  member-diff gates aligned as Warpline evolves.

## Next (shaped, decreasing certainty)

- **Rung 1 — spine completion** — self-healing SEI re-resolution and auto
  edge-snapshot capture, so SEI-keyed joins and the headline reads stop silently
  degrading.
- **Rung 2 — diagnostic capabilities** — the co-change graph, verification-freshness
  tracking, and lighting up the Wardline (risk) and Legis (governance) enrichment
  on the reverify worklist.
- **Federation conformance oracle inclusion** — Warpline's 14 golden vectors join
  the GS-7 four-member oracle as a fifth producer.

## Later (directional bets, no order, no dates)

- **Rung 3 — predictive** — empirical blast radius, preflight prediction, and
  time-aware risk-trajectory scoring.
- **Rung 4 — temporal fabric** — counterfactual graph reconstruction, ownership
  drift, fleet-wide temporal impact, and semantic change typing.
- **Rename and lineage continuity** — settle the C′/A′ locator-rename source once a
  proven need exists; largely subsumed by Rung 1 re-resolution (re-resolving to the
  current SEI makes renames Loomweave's problem, already solved).
