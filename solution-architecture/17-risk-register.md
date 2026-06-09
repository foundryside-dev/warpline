# Risk Register

Likelihood/Impact: H/M/L. "Impact" is product blast radius (kills the concept,
breaks doctrine, or wastes the spike), not security posture (re-derived per the
deconfliction-first lens).

| ID | Risk | L | I | Mitigation / response | Trace |
|----|------|---|---|------------------------|-------|
| RSK-01 | **Forbidden-aggregator drift** (doctrine §6): temporal snapshots slide into mirroring "now"; Heddle becomes the de-facto read path for structural truth | M | H | ADR-0004 firewall (stored / never-stored / never-answered lists); spike doctrine review is a named gate; reversal trigger in ADR-0004 routes evidence to owner instead of widening scope | CON-ORG-01; spike Q1/Q3 |
| RSK-02 | **Loomweave read surface insufficient** for edge snapshotting, and the fix would need member-side code — frozen pre-launch (CON-TEC-02) | M | H | spike Q1 verifies against SOURCE first (docs are known-drifted); if insufficient: wait-for-cutover or no-go, never a member patch; finding feeds the post-launch loomweave backlog as that member's own ticket | `15-` Phase 0; ADR-0002 |
| RSK-03 | **Charter seam collision** — "what is impacted" reads as Charter's question (doctrine §2); §7 Q1 (ONE bounded thing) fails at admission review | M | M | seam stated in `00-`/`04-` (structural/temporal vs obligations slice; Charter consumes Heddle); explicit seam section required in the spike report; owner adjudicates at §7 | spike Q3 |
| RSK-04 | **Solo mode loses the grep test** — locator-keyed history without SEI isn't preferred over grep, so §7 Q2 (useful alone) fails | M | M | ADR-0003 measures lossiness honestly; outcomes are narrow-the-claim or no-go — never quietly requiring Loomweave | spike Q4; admission bar (b) |
| RSK-05 | **False-negative blast radius** — stale/thin snapshots cause agents to skip re-verification of genuinely affected code (worse than no tool: false confidence) | M | H | staleness + completeness mandatory on every answer (`11-` Q3); NFR-06 planted-change corpus before any agent-facing release; depth-bounded claims only | NFR-06 |
| RSK-06 | **Tree-cleanliness regression** — store/scratch lands in the analyzed repo, dirtying trees and blocking legis signing (precedent `weft-d822a7de2d`) | L | M | placement outside the working tree decided up-front (ADR-0004 §4, `13-`); CI `git status --porcelain` assertion | NFR-05 |
| RSK-07 | **Scope leak into the frozen members** — "just a tiny patch" in loomweave/filigree during the spike breaches the owner directive and destabilizes the launch | M | H | hard rule in `15-` Phase 0 (stop + report, no exceptions); review check in `14-` (zero member-repo diffs) | CON-TEC-02 |
| RSK-08 | **Drifted-docs design inputs** — sibling-surface facts taken from hub docs are wrong; design built on a surface that doesn't exist | M | M | all sibling facts carry `[ASSUMED]`; spike's first task is source-grounding (Q1); standing rule: verify against executable source | `00-` assumptions 1–4 |
| RSK-09 | **Spike rots into a commitment** — workspace exists for months, becomes treated as a decided member without the §7 ruling | L | M | ADR-0001 60-day expiry (2026-08-09) + "go = recommendation, not admission" stated in README/ADR-0001 | CON-ORG-02 |
| RSK-10 | **Name/vocabulary leak** — placeholder name or unblessed field names freeze into wire shapes | L | L | D-09 reactivation gate: glossary clearance before any wire freeze; `11-` marks all names provisional | CON-ORG-03 |
