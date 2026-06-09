# Integration Plan

Greenfield system, brownfield *ecosystem*: Heddle touches no sibling's code,
but it reads two external surfaces and (post-launch) is read by four. Every
integration below is enrich-only in BOTH directions by construction.

## Phase 0 — spike (now, pre-cutover; CON-TEC-02 in force)
| Seam | Direction | Contract | Reality check |
|------|-----------|----------|---------------|
| Git repo | Heddle ← git | `git log` / `git diff` plumbing; post-commit hook installed by `heddle init` in the *analyzed* repo (the hook is Heddle's file, not a member change) | stable, versioned, the one hard dependency |
| Loomweave read surface | Heddle ← loomweave (OPTIONAL) | `[ASSUMED]` a published catalog/edge read surface exists and is sufficient — **spike Q1 verifies against loomweave source, not docs** (suite docs are known-drifted) | THE open integration risk (RSK-02); if no sufficient surface exists, the options are wait-for-cutover or no-go — NOT a member-side change |

Spike-phase rule: if any Phase-0 step turns out to need a diff inside
filigree/wardline/legis/loomweave, the step stops and the finding goes in the
spike report as a constraint conflict. No exceptions, no "tiny" patches.

## Phase 1 — post-cutover, post-go, post-admission (all three required)
Each consumer seam is a ticket in THAT member's tracker, counterparted to the
hub per convention; each is that member's choice to adopt, on its own release
line. Heddle never requires any of them (doctrine §5).

| Consumer | Pull | Coherent pair story without others |
|----------|------|-------------------------------------|
| Loomweave | churn/recency per entity → `high_churn`, `recently_changed` go live | yes — structural truth + its own history |
| Charter | re-verify worklist for obligation re-verification | yes — obligations + what moved |
| Legis | gate scope: which attestations does this range invalidate | yes — provenance + blast radius |
| Wardline | scoped re-scan set instead of full-repo scan | yes — policy + where to look |
| Filigree | worklist filed as issues; shared actor-string vocabulary | yes — work state + what changed |

Phase-1 wire shapes freeze only after glossary clearance (D-09) and entry into
the federation conformance-oracle corpus (GS-7 line) — contract-first, the
lesson the current launch is paying for.

## Failure modes at the seams (designed responses)
- Loomweave surface unreadable mid-ingest → snapshot recorded as `SKIPPED(reason)`, ingest continues locator-keyed; next successful read upgrades (ADR-0003).
- Loomweave schema/version drift → version probe on every read; mismatch = `SKIPPED(version_mismatch)`, surfaced on next query — never a crash, never a guess.
- Hook failure → exit 0 always; failure logged in-store, surfaced on next query (`11-` I2). A broken Heddle must never block a commit.
- Stale snapshots → staleness stamp mandatory on every blast-radius answer; thin answers look thin (NFR-06).
