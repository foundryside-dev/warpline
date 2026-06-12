# PRD-0001 - Agent-First MCP Productization

Status: ready-for-planning
Decision: PDR-0001
Bet (roadmap.md): Now
Target metric (metrics.md): Agent impact answer success rate

## Problem

Coding agents working in Weft member repos need to decide what changed, what may
be affected, and what to reverify before they claim work is complete. Today that
job falls back to manual grep, memory, raw git inspection, or human judgment.
Heddle has enough implementation to answer the job, but it must be productized
around the MCP surface because agents experience Heddle primarily through
`tools/list` and structured tool calls, not through architecture documents.

## Success metric

Agent impact answer success rate reaches 8 of 10 dogfood diffs with solo-mode
parity against existing tools through MCP in 2 tool calls or fewer, and 8 of 10
federation-enriched dogfood diffs with a better answer than existing tools
before admission recommendation.

Baseline: not yet measured as a 10-diff dogfood run. Planted corpus and contract
tests pass as of 2026-06-13.

## Acceptance criteria (falsifiable)

1. SUCCESS - An agent starting from MCP `tools/list` can discover the core flow
   and answer changed-set plus reverify context with solo-mode parity against
   existing tools for at least 8 of 10 dogfood diffs in 2 tool calls or fewer.
   Reject branch: If an agent must inspect raw SQLite or manually grep for more
   than 2 of 10 solo-mode dogfood diffs, the bet is rejected and an MCP refactor
   plan is opened.
2. FEDERATION UPLIFT - When federation member enrichment is available, at least
   8 of 10 federation-enriched dogfood diffs produce a more actionable answer
   than existing tools alone.
   Reject branch: If enriched answers are merely equal to existing tools, the
   federation value claim is unproven and the bet is rejected.
3. MCP STRUCTURE - Every core MCP response includes schema/version, query
   metadata, enrichment state, warnings when degraded, and actionable next-step
   fields where applicable.
   Reject branch: any core response that returns opaque text without structured
   recovery fields blocks acceptance.
4. FEDERATION BOUNDARY - Heddle responses identify absent, stale, skipped, or
   no-snapshot enrichment without claiming sibling-owned current truth.
   Reject branch: any response that treats Loomweave, Charter, Legis, Wardline,
   or Filigree data as Heddle-owned truth blocks acceptance.
5. SOLO MODE - With no sibling enrichment, Heddle still returns useful
   locator-keyed changed/timeline/reverify facts and explicit `NO_SNAPSHOT` or
   absent enrichment state.
   Reject branch: sibling absence causing crash, empty ambiguity, or hidden
   degradation blocks acceptance.
6. RELEASE HYGIENE - The release-candidate gate passes with member-diff guard,
   spike harness, productization gate, lint, types, and tests.
   Reject branch: any Heddle-caused sibling repo diff or failing gate blocks
   acceptance.

## Non-goals (this bet)

- Do not declare federation admission.
- Do not patch sibling repos.
- Do not design pricing, hosting, telemetry, or external release posture.
- Do not turn Heddle into a tracker, governance gate, trust engine, or current
  structure authority.

## Constraints & guardrails

- Heddle must remain local-first and read-only against analyzed repos.
- Missing sibling data must degrade honestly and explicitly.
- MCP deficiencies are P0 product defects; they are not documentation polish.
- A broken Heddle hook must never block a commit.
- Heddle-owned draft contracts remain non-normative until owner admission and
  glossary clearance.

## Open questions / assumptions

- A 10-diff dogfood corpus still needs to be selected.
- `tools/list` descriptions may need to become more workflow-oriented after
  usability review.
- The current MCP server emits JSON inside text content; acceptance should
  decide whether that is acceptable under Weft MCP norms or requires refactor.

## Handoff

- Product owns this PRD, acceptance criteria, and the value verdict.
- Planning owns the executable implementation plan for any MCP refactor.
- Solution architecture owns any changes to server shape, schema versioning, or
  contract-freeze posture.
- Program-management owns sequencing if multiple productization slices compete.
