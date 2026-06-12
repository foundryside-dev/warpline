# PDR-0001 - Move Heddle To Product-Candidate Ownership

Date: 2026-06-13
Status: accepted
Author: Codex product owner
Owner sign-off: request to take ownership on 2026-06-13; admission still reserved
Supersedes: none
Related: `roadmap.md` (Now), `metrics.md` (north-star), `spike/REPORT.md`

## 2026-06-13 Readiness Addendum

A later live review found that Heddle is a disciplined solo-mode prototype but
not product-ready or member-grade. This does not reverse the ownership posture;
it narrows it. Heddle remains a first-class product bet, but productization and
admission recommendations are blocked until production SEI resolution,
production edge snapshot capture, MCP usability, C-9/C-13 runtime conformance,
and federation uplift are proven by executable dogfood evidence.

## Context

Heddle has a useful prototype scaffold, core CLI/MCP surfaces, honest
`NO_SNAPSHOT` behavior, reverify worklists, and Heddle-owned draft federation
contracts. The remaining risk is no longer "can a prototype exist"; it is
whether Heddle is treated as a coherent product whose MCP surface is at least as
good as existing tools in solo mode, better with federation members, and whose
federation posture does not blur sibling authority boundaries.

## Options considered

1. Keep Heddle as a spike-only architecture workspace.
   - Pro: avoids overclaiming admission.
   - Con: leaves product intent, metrics, and MCP UX bar implicit.
2. Move Heddle to a product-candidate ownership posture.
   - Pro: creates durable vision, roadmap, metrics, PRD, and decision
     provenance while preserving owner-reserved admission.
   - Con: requires ongoing checkpoint discipline.
3. Declare Heddle an admitted Weft member now.
   - Pro: gives the design a clear label.
   - Con: violates the owner-reserved admission boundary.

## The call

Move Heddle to product-candidate ownership posture. Heddle is treated as a
first-class product candidate inside this repo, with MCP and federation design
as primary product surfaces. Heddle is not admitted to the Weft federation by
this decision.

## Rationale

Option 2 is the only option that solves the real product gap without crossing
the authority boundary. It makes the bet falsifiable: if MCP is not at least as
good as existing tools in solo mode and better with federation members, Heddle
fails as a product candidate no matter how much implementation exists. It also
makes sibling boundaries testable by keeping Heddle-owned contracts and consumer
tickets separate from sibling-owned work.

## Reversal trigger

Reopen this decision if any of the following happens:

- 3 consecutive dogfood diffs require manual grep or raw store inspection after
  an agent starts from MCP `tools/list`.
- A core query lacks structured recoverable MCP output for absence, staleness,
  or degraded enrichment.
- Heddle implementation requires patching a sibling repo before owner admission.
- The owner rejects Heddle admission after reviewing the product-candidate
  evidence.
