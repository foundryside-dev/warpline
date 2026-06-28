# Current State - Warpline

Checkpoint: 2026-06-29 — branch `release/1.2.0` (a 1.3.0-worth of accepted capability
built atop v1.2.0; the version cut + release is the open owner escalation)

## The bet right now

**Cut + release the `release/1.2.0` stack.** Spine hardening shipped as **v1.2.0**
(PDR-0006). Since then, atop `release/1.2.0`, four accepted capabilities have landed and
the four-member federation seam is now fully lit:

- **Verification-freshness** (PDR-0005 → accepted PDR-0007) — `last_verified` trust-decay
  axis, merged (4b94705), validated on a real repo against its reversal trigger.
- **Rung-2 "light up the inert dimensions" — DONE (PDR-0008).** All four `include_federation`
  members are now real reverify consumers: filigree (work), wardline (risk, attest-2),
  legis (governance, `governance_read.v1` — committed), and **plainweave (requirements,
  `weft.plainweave.requirements_enrichment.v1`)** — the dimension warpline had never wired.

The capability is built and accepted; what remains is the **version cut (1.3.0 vs 1.2.x)
and the public-release-status change** — an owner escalation (below).

## Branch / release state

- **`main` = v1.2.0** (spine hardening; PDR-0006).
- **Working branch = `release/1.2.0`** — carries v1.2.0 + verification-freshness +
  attest-2 risk + legis governance + `project_status` + D1 impact_completeness (all
  committed) and now the **requirements consumer (UNCOMMITTED, PDR-0008)**.
- **Identity (standing requirement):** git/gh identity is **tachyon-beep** (active);
  johnm-dta inactive. Verify before any commit.

## In flight

- **Plainweave requirements consumer (PDR-0008) — built + accepted, UNCOMMITTED.** ⚠️
  `commands.py` is **co-mingled** with a *concurrent* (not this owner's) observability /
  loomweave work-stream — U2/U3/U4: `log_health`, breadcrumbs, `store.py`, `loomweave.py`
  `max_frame_bytes`, `test_loomweave_probe.py`, `test_reresolve.py`,
  `test_commands_reliability.py`. Do **not** `git add -p` to untangle while that agent may
  still be editing (silent-work-loss hazard; `git stash` is operator-blocked). No tracker
  item — driven by the owner-gated plainweave handoff; captured in PDR-0008. Full suite
  569 passed / 1 skipped / 0 failed; ruff + `mypy src` clean.
- `warpline-17242c627b` (P3) — atomic ROLLBACK coverage + no-open-transaction precondition.
  **OPEN — clean, startable** (last ungated 1.2.0 follow-up).
- `warpline-9eae3eb86a` (P3) — Charter→Plainweave sibling-guard evidence refresh. Was gated
  on the local `plainweave` repo being present; **plainweave IS present at
  `/home/john/plainweave`, so the gate is now liftable** — reconfirm before claiming.
- Observation `warpline-obs-da4909ac64` (P3): bare-`assert`-under-`-O` in `mcp.py`
  inputSchema guard (expires 2026-07-09 unless promoted).

## Open questions / blocked-on-owner (escalations)

1. **Cut + release the `release/1.2.0` stack** — version cut (1.3.0 vs 1.2.x) and the
   public-release-status change outside this repo. Owner's call (grant: "changing
   public/user-facing release status outside this repo"). Now includes the requirements
   consumer once committed.
2. **Commit strategy for the requirements consumer** — `commands.py` co-mingles this work
   with a concurrent observability work-stream. Commit both together, or coordinate with
   the other agent and split into two commits? Owner's call; do not untangle unilaterally.
3. **5th-producer hub handover** — outward-facing/sibling. warpline-side package done;
   GS-7 oracle wiring + glossary freeze (OD-5) remain. Owner's call.
4. **(deferred)** Promoting `requirements`/`verification` into the frozen closed envelope
   vocab — future contract/glossary escalation (v1 keeps both as reverify-item fields;
   PDR-0005, PDR-0008).

## What this checkpoint did

- **PDR-0008** — accepted the Plainweave requirements consumer (4th federation member)
  after a 4-lens adversarial review (10/14 findings confirmed; a HIGH no-silent-clean bug
  — `unavailable`→`absent` collapse for per-entity-unavailable / SEI-less entities — found
  and fixed). Autonomous under the grant (accept reversible repo-local work).
- **Reconciled the stale 2026-06-26 brief** to present reality: the bet then was
  verification-freshness-built-unreleased on `plan/verification-freshness`; it is now
  accepted (PDR-0007) and merged into `release/1.2.0`, which carries the full
  four-member-federation stack.
- **roadmap.md** — Rung-2 "light up inert dimensions" marked DONE (all four members live);
  Updated stamp (PDR-0008). **metrics.md** — 2026-06-29 reading: federation member coverage
  3→4; no reversal trigger crossed.

## Next session starts here

Owner decision on **escalation #1/#2** — how to commit + cut/release the `release/1.2.0`
stack given the co-mingled `commands.py`. Failing that, the two clean repo-local pickups:
`warpline-17242c627b` (atomic ROLLBACK coverage) or `warpline-9eae3eb86a` (Charter→Plainweave
evidence — now ungated, plainweave present).
