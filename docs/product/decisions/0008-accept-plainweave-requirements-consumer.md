# PDR-0008 - Accept the Plainweave Requirements-Enrichment Consumer (the 4th federation member) After Adversarial Review

Date: 2026-06-29
Status: accepted
Author: Claude (product owner session)
Owner sign-off: autonomous under the `vision.md` grant — "accept or reject delivered
work against `metrics.md` and PRD criteria" and "dispatch implementation planning for
reversible, repo-local Warpline work." This PDR records ACCEPTANCE of an already-built,
repo-local capability; it does **not** commit or release it. The commit/merge/release of
the `release/1.2.0` stack (now incl. this work) is an **open owner escalation** — see
`current-state.md`.
Supersedes: none
Related: PDR-0007 (verification-freshness, same `release/1.2.0` stack), the lit
wardline-attest-2 + legis `governance_read.v1` consumers (the sibling "light up inert
dimensions" Rung-2 work this extends), `roadmap.md` (Rung 2 — "light up the flagship's
inert dimensions"; the temporal COP `include_federation` seam), the producer-side
plainweave handoff
(`<plainweave>/docs/handoffs/2026-06-28-warpline-requirements-enrichment-consumer-impl.md`).

## Context

The reverify worklist's `include_federation` seam carries a closed 6-key enrichment vocab.
Three members were live consumers (filigree work, wardline risk via attest-2, legis
governance via `governance_read.v1`); **`requirements` was the one dimension warpline never
wired** — it rode as the reserved `disabled`/`unavailable` default. Plainweave (the
requirements owner per the federation authority split) shipped its producer side — a
`plainweave requirements-enrichment <refs> --json` CLI + a frozen golden
`weft.plainweave.requirements_enrichment.v1` — and authored an owner-gated sibling handoff
asking warpline to wire the consumer. The owner directed the build via `/goal`.

This is a **Rung-2 "light up the flagship's inert dimensions"** capability landing (the
4th of the four federation members now a real consumer), structurally identical to the
legis member: a capability-gated CLI read client, an honest per-member `weft-reason`, and
an advisory per-entity + envelope-scalar enrichment that never gates.

## The call

**ACCEPT the Plainweave requirements consumer.** Built end-to-end mirroring the legis
member, verified against every handoff acceptance criterion and hard invariant, and
hardened by an adversarial multi-agent review before banking. The work is repo-local and
reversible; acceptance is within the grant. RESERVED-SHAPE: the requirement *item* schema
is proposed-but-unratified (sibling interface-lock prompt #3), so the consumer treats item
bodies OPAQUELY and the contract test is structure/status-pinned, not byte-pinned — proving
*consumption* without freezing an unratified internal shape.

## Validation evidence

- **Six acceptance criteria + five hard invariants, each with a dedicated test**
  (`present`/`absent`/`unavailable` scalars + per-item array; `disabled`+transport-blocker
  when the verb is absent; member never omitted; advisory-never-gates; opaque
  identity/items; local-only seam; no-silent-clean).
- **Adversarial 4-lens review** (no-silent-clean, legis-parity, opacity/local-only/advisory,
  test/contract rigor): 14 candidate findings → **10 confirmed** after independent
  refute-first verification. All confirmed findings that were *this work's* were fixed:
  - **HIGH (honesty)** — a reachable producer returning per-entity `unavailable`, OR a
    worklist entity warpline cannot resolve to a SEI (identity-unresolved), was collapsing
    to envelope `absent` with an *affirmatively false* reason ("plainweave found none
    bound"). Fixed with a plainweave-specific scalar (`unavailable_seen`) that never
    collapses `unavailable`→`absent` — the load-bearing no-silent-clean invariant.
  - **MEDIUM** — contract test couldn't catch envelope-wrapper drift (it hand-built the
    `{ok,data}` wrapper) → added a guard parsing a **real captured CLI envelope** verbatim;
    added the previously-untested "producer reachable but omitted a ref" branch.
  - **LOW** — stale `cop.py` docstrings; local-only-seam (HI4) and the
    `available()==False → disabled` capability-gate path now pinned.
- **Suite green**: 41 requirements-scoped tests + every suite exercising the shared
  `commands.py` hunks pass (126 in that scope); full warpline suite **569 passed, 1
  skipped, 0 failed**; ruff clean on the changed files; `mypy src` clean.

## What this acceptance does NOT cover (still owner-reserved)

- **Commit / merge / release.** The work is **uncommitted** on `release/1.2.0`, and
  `commands.py` is **co-mingled** with a *concurrent* agent's observability/loomweave
  work-stream (U2/U3/U4 — `log_health`, breadcrumbs, `store.py`, `loomweave.py`
  `max_frame_bytes`, `test_loomweave_probe.py`, `test_reresolve.py`,
  `test_commands_reliability.py`). Untangling that mid-edit risks silent work loss; the
  commit strategy and the public-release-status change (the version cut for the whole
  `release/1.2.0` stack) are the owner's call. See `current-state.md`.
- **Byte-pinning the contract test.** Deferred until the requirement item schema is
  ratified (interface-lock prompt #3); the structure/status pin is the correct discipline
  pre-ratification.
- **Patching plainweave.** None done — warpline only READ the producer and vendored a
  *copy* of its golden into warpline's own fixtures (warpline-local, not a sibling patch).

## Reversal trigger

Reopen if **either**: (a) over real federated use the requirements dimension perpetually
reads `disabled`/`unavailable` because the installed plainweave never advertises
`requirements-enrichment` in member repos — i.e. the consumer works but the producer is
never present, so the axis adds no signal (mirrors PDR-0007's "never used" trigger,
watched via the `metrics.md` federation-member-coverage reading); or (b) the requirement
**item** schema is ratified in a shape that diverges from the vendored golden such that the
structure/status contract test fails — at which point the consumer and the (then
byte-pinned) contract test must be reworked.
