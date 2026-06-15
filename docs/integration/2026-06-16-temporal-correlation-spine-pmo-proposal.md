# PROPOSAL (for PMO / owner review) — Temporal Correlation Spine

**Date:** 2026-06-16
**Author:** Warpline product-owner session
**Status:** **ADOPTED — sponsored in full by the foundation (PDR-0025, 2026-06-16),
with three PM conditions.** Warpline is ratified as owner of the temporal-episode
axis (domain extension, not a new member, not a second identity authority).
Steps 1–2 (repo-local capture + reconstruction demo) are authorized as Warpline
autonomy under the ratified contract; the cross-member stamping convention remains
hub-authored and incrementally adopted (no sibling obligation freezes until the hub
authors it against Warpline's demonstrated reconstruction). The demo is now a
**validation/shaping gate, not go/no-go**. See `~/weft/pm/product/decisions/0025-sponsor-warpline-temporal-correlation-contract.md`
and warpline `docs/product/decisions/0003-hub-ruling-pdr-0025-relay.md`.

> **PM conditions (must hold):** (1) the demo must exercise the **squash-merge/rebase**
> case, not a clean-history fixture; (2) define the **episode boundary** (resolving
> toward *episode ≈ work-session*) with an honest dirty-tree/detached-HEAD fallback;
> (3) **sequencing fence** — this is Rung-3/token-tier and sits *behind* the
> four-member launch cutover and Warpline's base-impl fast-follow.
**Audience:** weft PMO / hub; owner (admission & authority-split decisions)
**Related:** `~/weft/doctrine.md` (PDR-0023 seams hub-authored; §5 enrich-only;
§10 honesty invariant), `~/weft/sei-standard.md` (locked identity spine),
`~/weft/uri-scheme.md` (no registry/broker — closed by SEI),
`~/weft/pm/2026-06-13-warpline-interface-lock.md` (proven-need gate),
`~/warpline/docs/product/roadmap.md` (temporal correlation spine; Rung 3).

---

## 1. Summary

A single logical change ripples across the federation: code moves, a Filigree
issue changes state, a Wardline finding appears, a Legis attestation is recorded,
the Loomweave graph shifts. Today **no member can reconstruct that bundle** —
"these meta-changes were attached to *this* change" — because the events siblings
emit do not carry the originating change's git anchor.

We propose a **hub-authored, hub-blessed convention**: *every member stamps the
originating `branch@sha` on the events it emits*, as optional metadata. Warpline —
the federation's temporal / change-impact authority — owns the **temporal-
correlation contract** (what the anchor means, what granularity, how the bundle
reconstructs) and performs the read-time join. **Git owns the key value; no member
mirrors another's data; no new identifier is minted.**

This is the mechanism behind Warpline roadmap Rung 3 (empirical blast radius): it
turns *"what actually broke when X changed"* from fuzzy time-window correlation
into a deterministic join.

**The payoff is a federation temporal common operating picture (COP).** With the
anchor in place, Warpline — as the temporal authority — answers a single
situational question for any frame (an edit, a rev range, a time window, a
`branch@sha`, a SEI): *"within this range, here's what everyone tells me they
changed"* — code, work-state, findings, attestations, graph deltas, **each
attributed to its owning member and composed at read time, never mirrored.** This
is the existing hub-blessed `include_federation` consult generalized from the
reverify worklist to the whole picture. Its honesty requirement is load-bearing:
the COP always renders coverage (who answered, who was unreachable, how stale) so
an unmonitored source never reads as "nothing changed."

## 2. Problem / opportunity

- The federation's value is the **seam** (PDR-0023). "What happened together" is a
  first-class seam question and currently unanswerable end-to-end.
- Warpline can already see *code* change anchored to a commit, but the sibling
  consequences are stranded in each member's own store with no shared correlation
  key, so a human/agent must eyeball timestamps to relate them.
- The fix is cheap because the key **already exists**: every member is operating
  inside a git working context (`branch@sha`) when it emits an event. We are not
  inventing identity — we are asking everyone to *write down the SHA they already
  have.*

## 3. The proposal

**The convention (hub-authored):** when a member emits a federation-relevant event
(issue state change, finding, attestation, graph delta), it records the
**originating `branch@sha`** — the working-context anchor at the moment the change
that triggered the event was made — as optional event metadata.

**Ownership split (doctrine-clean):**

| Concern | Owner |
|---|---|
| The key *value* (`branch@sha`) | **git** (no member mints it) |
| The temporal-correlation *contract* (anchor semantics, granularity, reconstruction) | **Warpline** (its temporal domain) |
| Each event's *payload* (the issue, finding, attestation, delta) | **the emitting member** (unchanged authority) |
| Entity identity (which entity) | **Loomweave / SEI** (unchanged) |

**Why this is not a second identity authority.** SEI identifies an *entity* (a
noun — *which* function; spatial; Loomweave's, LOCKED). The correlation anchor
identifies a *change episode* (a verb-moment — *which act of changing*; temporal).
Orthogonal axes that compose: an episode touches a set of SEIs. Warpline claims
the temporal axis only and refuses, as ever, to become a second entity-identity
authority.

## 4. Doctrine compliance

- **Enrich-only (§5).** The stamp is **optional metadata**. A sibling's core flow
  (filing an issue, emitting a finding) never depends on Warpline to produce the
  key, and absence degrades to "uncorrelated," never to a failure. Removing
  Warpline breaks no member.
- **Hub-authored / hub-blessed (PDR-0023).** Warpline does **not** dictate this to
  siblings peer-to-peer. It is proposed *to the foundation*; the hub authors the
  convention and blesses the seam.
- **Proven-need gate.** Warpline earns the ask before billing four members for it
  (see §6 sequencing). No sibling obligation freezes on a merely-claimed need.
- **Honesty invariant (§10 / `weft-reason`).** An unstamped or unjoinable event
  reconstructs as *honestly partial* (`cause + reason_class + fix`), never as "no
  related changes."
- **Not a registry/broker (`uri-scheme.md`).** This adds no `weft://` scheme, no
  central broker, and no shared store. It is a *convention to stamp an existing git
  value* plus a read-time join. This adjacency to the owner-closed decision is
  called out explicitly for the owner to confirm the distinction holds.

## 5. The ask of each member (illustrative — subject to hub authoring)

| Member | Event it emits | Stamp |
|---|---|---|
| Filigree | issue state change, claim, close | originating `branch@sha` on the event/annotation |
| Wardline | finding, waiver, judge label | originating `branch@sha` on the finding record |
| Legis | attestation, sign-off, CI/check context | originating `branch@sha` on the attestation |
| Loomweave | analyze run / graph delta | the analyzed `branch@sha` (already partly present as `git_sha`) |

In every case the member already holds the SHA; the ask is to *persist it as
correlation metadata*, not to compute anything new.

## 6. Sequencing & gates (proven-need)

1. **Warpline-local capture** *(repo-local; Warpline autonomy — no escalation):*
   record `branch + HEAD SHA + detection timestamp` as the working-context anchor
   on each detected change. Today the store keeps only the *introducing*
   `commit_sha`, with no `branch` and no detection-context anchor.
2. **Demonstrate reconstruction** from the anchors Warpline can already see (its
   own change events + any sibling events that happen to carry a commit), proving
   the bundle is useful even before universal stamping.
3. **Take the proven need to the PMO** — *this document.*
4. **Hub authors + blesses the convention**; members adopt incrementally
   (enrich-only, so partial adoption already yields partial bundles).

Steps 1–2 are Warpline's to execute now; steps 3–4 are the owner/hub decision this
proposal requests.

## 7. Cost & risk

- **Cost: low.** Each member persists a SHA it already has. No new service, no
  runtime dependency, no schema authority transfer.
- **Risk — history rewrite (the real one; PDR-0025 condition 1).** Squash-merge and
  rebase **rewrite SHAs**: squash collapses N feature-branch commits into one *new*
  mainline SHA and the branch is usually deleted, so **every `branch@sha` stamped
  during the episode is orphaned the instant the PR merges** — and squash is a
  *default* merge mode, not an edge case. **Correction (PM, PDR-0025):** the earlier
  draft's candidate — "reconcile via the Legis→Loomweave rename/rewrite signal" —
  **conflated two different operations.** A *rename* (path→locator, Loomweave-owned,
  PDR-0021) is **not** a *SHA-rewrite*; the rename feed carries no rewrite
  reconciliation. SHA-rewrite reconciliation is the genuinely-unowned, load-bearing
  question, and **the demo must bite there** (a representative squash-merge fixture,
  not clean history). **Candidate to test (not prescribed — Warpline's contract to
  shape):** Legis is the PR/CI authority that actually *observes the merge*, so it
  could emit a **merge-mapping** — `{squashed-away SHAs} → {new mainline SHA}` —
  distinct from the rename feed and on-charter for Legis (itself a future
  hub-blessed seam under prove-the-need). The demo's job is to show whether
  reconstruction *needs* that signal or survives on `branch` + episode-boundary
  alone.
- **Risk — granularity.** Per-commit vs per-push vs per-work-session. Too fine
  fragments a logical change; too coarse blurs unrelated work.
- **Risk — dirty tree / detached HEAD.** Uncommitted work and detached HEAD have no
  clean `branch@sha`; the contract needs an honest fallback (and an honest
  `reason_class`).

## 8. Decision requested

1. Does the PMO/owner sponsor a **Warpline-owned temporal-correlation contract** as
   a domain extension (temporal-episode axis, orthogonal to SEI)?
2. Approve the **proven-need sequence** (§6) — Warpline ships local capture +
   reconstruction *before* any sibling ask.
3. Bless, *in principle and pending Warpline's demonstration*, the hub-authored
   **"stamp the originating SHA"** convention, to be authored by the hub (not by
   Warpline) when the need is proven.

## 9. Out of scope / what this is NOT

- Not a shared cross-member store; not a federation aggregator.
- Not a new minted identifier or a `weft://` scheme or a broker.
- Not a Warpline mandate on siblings — the hub authors the convention.
- Not a gate: correlation is advisory enrichment, never an allow/deny verdict.
