# PDR-0003 - Hub Ruling Relay: PDR-0025 Sponsors The Temporal-Correlation Contract

Date: 2026-06-16
Status: accepted
Author: Claude (product owner session)
Owner sign-off: this is a relay of the foundation's owner ruling (PDR-0025); no new
warpline authority is claimed here. Recording the ruling in warpline's decision log
is autonomous under the `vision.md` grant ("append Product Decision Records").
Supersedes: none
Related: `~/weft/pm/product/decisions/0025-sponsor-warpline-temporal-correlation-contract.md`,
`docs/integration/2026-06-16-temporal-correlation-spine-pmo-proposal.md`,
`roadmap.md` (temporal correlation spine + COP), PDR-0002 (capability ladder),
`~/weft` PDR-0021 / PDR-0023 / PDR-0024, `~/weft/uri-scheme.md`.

## Context

Warpline authored the "Temporal Correlation Spine" proposal (2026-06-16) and took it
to the foundation. The foundation answered with **PDR-0025**. This PDR carries that
ruling back into warpline's workspace so the warpline session operates under the
ratified contract and none of the attached conditions is lost.

## The ruling (PDR-0025, owner, 2026-06-16)

- **Sponsored in full, now.** Warpline is ratified as **owner of the
  temporal-episode axis** — the temporal-correlation contract (anchor semantics,
  granularity, reconstruction). A **domain extension** within warpline's
  already-admitted temporal/change-impact authority; **NOT** a new member and
  **NOT** a second entity-identity authority (SEI stays Loomweave's single
  authority; the episode axis is orthogonal).
- **Owner overrode the PM's "bless-in-principle-pending-demo" default.** The
  authority is granted ahead of the demonstration, so **the demo is a
  validation/shaping gate, not a go/no-go gate.**
- **No-broker line holds (owner-confirmed).** Stamping an existing git value on each
  member's own events + a decentralized read-time join is enrich-only metadata — no
  central store, no minted identifier, no broker, no `weft://` scheme. The
  owner-closed `weft://` decision is not reopened.

## What this authorizes vs. what still gates

- **Authorized now (no further sign-off):** steps 1–2 — repo-local capture
  (`branch + HEAD SHA + detection timestamp` working-context anchor; today the store
  keeps only the introducing `commit_sha`) and a reconstruction demonstration. Sits
  *behind* the launch cutover and warpline's base-impl fast-follow (see condition 3).
- **Still gated:** the cross-member "stamp the originating SHA" convention is
  authored **hub-side** and adopted **incrementally**; no sibling obligation freezes
  until the hub authors it against warpline's demonstrated reconstruction.

## PM conditions carried (all three)

1. **Squash-merge/rebase is the demo's load-bearing case** — not clean history.
   Squash collapses N commits into one new mainline SHA (branch deleted), orphaning
   every stamped anchor at merge. This is a *SHA-rewrite*, distinct from a *rename*
   (PDR-0021, Loomweave-owned, path→locator) — the rename feed carries no rewrite
   reconciliation. (Corrects the proposal's original §7 conflation.) Candidate to
   test, not prescribed: a **Legis merge-mapping** `{squashed-away SHAs} → {new
   mainline SHA}` (Legis observes the merge; a future hub-blessed seam under
   prove-the-need) vs. surviving on `branch` + episode-boundary alone.
2. **Define the episode boundary** — resolves toward *episode ≈ work-session* (not
   per-commit), with an honest `weft-reason` fallback for dirty-tree / detached-HEAD.
3. **Sequencing fence** — Rung-3 / token-tier; must not compete with the four-member
   launch cutover or warpline's base-impl fast-follow; steps 1–2 are cheap and
   parallelizable, capacity permitting, behind both.

## Reversal trigger

Inherits PDR-0025: revisit if warpline's reconstruction demonstration fails to
produce a useful bundle on a **rewritten-history (squash-merge)** fixture, or if the
read-time join cannot stay decentralized (a member forced to become a central join
store would breach the no-broker confirmation and reopen PDR-0025).
