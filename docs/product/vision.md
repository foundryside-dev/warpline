# Vision - Heddle

## Purpose

Heddle makes change impact mechanically answerable for local coding agents. Given
a diff or commit range, an agent should be able to ask what changed, who changed
it, what may be downstream-affected, and what must be reverified without
falling back to manual grep or human blast-radius review.

Heddle owns temporal change-impact facts. Heddle does not own the present-time
shape of the codebase or the federation's operational systems of record.

## Who it serves

- Primary: autonomous and supervised coding agents working inside Weft member
  repos who need a structured, local answer before they claim work is complete.
- Secondary: the human owner and sibling maintainers who need lower supervision
  load, clearer reverify prompts, and cleaner post-admission integration seams.
- Explicitly not: hosted analytics users, generic project-management users,
  teams that want Heddle to replace Loomweave, Filigree, Wardline, Legis, or
  Charter.

## Positioning

For local agents changing Weft member code who need reliable change-impact
context, Heddle is a local-first temporal change-impact authority that returns
structured changed-set, timeline, blast-radius, and reverify answers through CLI
and MCP, unlike manual grep or point-in-time graph tools, because Heddle stores
dated entity change facts and dated edge snapshots while preserving sibling
authority boundaries.

## Federation authority

Heddle owns temporal change-impact facts:

- entity-level change events from git history and hook-fed ingest
- dated edge snapshots read from published sibling surfaces
- honest staleness, completeness, and enrichment state
- agent-consumable reverify worklists derived from those facts

Sibling authority boundaries are product doctrine, not implementation detail:

- Loomweave owns current structure and SEI.
- Charter owns obligations, baselines, verification evidence, and requirement
  impact.
- Legis owns governance, sign-offs, CI/check context, and attestations.
- Wardline owns trust policy, findings, baselines, waivers, judge labels, and
  attestations.
- Filigree owns work state, issue lifecycle, claims, and close gates.

Heddle does not own work state, trust policy, governance, or obligations.

## Anti-goals

- Do not become a federation aggregator or shared cross-member store.
- Do not answer current structure as Heddle truth; query Loomweave or degrade.
- Do not auto-file, auto-close, allow, block, sign off, waive, or adjudicate.
- Do not require sibling installation for the core local workflow.
- Do not hide absence, staleness, or degraded enrichment.
- Do not ship an MCP surface that is worse than existing tools in solo mode or
  fails to become better with federation members.
- Do not become hosted telemetry, SaaS analytics, or a public service.

## Authority grant

Granted by: john, via product-ownership request on 2026-06-13
Last reviewed: 2026-06-13
Review cadence: every material strategy change or before federation admission

Autonomous within strategy - the agent MAY, without asking:

- maintain these product artifacts and append Product Decision Records
- write PRDs and falsifiable acceptance criteria
- refine Heddle-owned pre-admission contracts and design docs
- dispatch implementation planning for reversible, repo-local Heddle work
- reject or reprioritize work that violates the authority boundaries above
- accept or reject delivered work against `metrics.md` and PRD criteria

Escalate BEFORE acting - the agent MUST get owner sign-off for:

- changing this vision, strategy, authority grant, or federation authority split
- declaring Heddle an admitted Weft member
- changing public/user-facing release status outside this repo
- patching sibling repos or creating work in sibling trackers
- deprecating a capability users or sibling products depend on
- any pricing, commercial, licensing, public announcement, external-party, or
  irreversible data action
