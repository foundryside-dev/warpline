# Current State - Warpline

Checkpoint: 2026-07-01 — branch `main` @ `v1.3.0` (**RELEASED**). The long-standing
release escalation is closed; the stack is shipped, tagged, pushed, and installed.

## The bet right now

**v1.3.0 is shipped (PDR-0010).** The Rung-2 diagnostic tier is complete and live on
`main`: verification-freshness (PDR-0007), the four-member federation seam — filigree
(work), wardline (risk/attest-2), legis (governance), plainweave (requirements) —
(PDR-0008), the `project_status` probe, and the arch-analysis Phase-2 reliability
hardening (PDR-0009). **Near-term intent** (roadmap Now): the **5th-producer hub
handover**; then **Rung 3 (predictive)**. The metric it serves: the north-star
federation-enriched reverify, now backed by the released stack.

## Branch / release state

- **`main` = `v1.3.0`** (merge `3768794`, annotated tag `v1.3.0`, pushed to origin;
  clean fast-forward). `git diff release/1.2.0 main` == empty — main holds exactly the release.
- **Installed:** `~/.local/bin/warpline` (+ `warpline-mcp`) = **1.3.0**; the live `.mcp.json`
  binary is current, and the stale `heddle`-venv shadow was retired (bare `warpline` = 1.3.0).
- **Identity (standing requirement):** git/gh identity is **tachyon-beep** — verified before
  every commit + the push this session.
- Legacy: the `release/1.2.0` branch carried the 1.3.0 release (name drift); `origin/release/1.2.0`
  is now behind. Optional cleanup (delete, or rename `release/1.3.0`).

## In flight

- `warpline-17242c627b` (P3) — atomic ROLLBACK coverage + no-open-transaction precondition.
  **OPEN — clean, startable** (last ungated 1.2.0 follow-up).
- `warpline-9eae3eb86a` (P3) — Charter→Plainweave sibling-guard evidence refresh. **Ungated**
  (plainweave repo present); reconfirm before claiming.
- Observation `warpline-obs-da4909ac64` (P3): bare-`assert`-under-`-O` in `mcp.py` inputSchema
  guard (expires 2026-07-09 unless promoted).
- **Sibling/federation work handed to the owner** (built at owner direction this session, NOT
  warpline-repo, uncommitted in the siblings): the **wardline `scan_manifest` producer seam**
  (+ delta-mode `--manifest-full-coverage` flag) that closes AMBER-2 / `weft-9a35aa00e7` so
  plainweave stops degrading. 3 wardline files (`scan.py`, `run.py`, `test_scan_artifacts.py`),
  tested + e2e-verified, **for you to commit**; plus plainweave fixture alignment and blessing
  `weft.wardline.scan_manifest.v1` hub-side.

## Open questions / blocked-on-owner (escalations)

1. **✅ RESOLVED (2026-07-01) — plainweave reshipped; the requirements member is LIVE.** The
   installed `plainweave` now advertises **and** serves `requirements-enrichment`, and warpline's
   `PlainweaveRequirementsClient.available()` returns **True** — the 4th member is WIRED (reads
   honest present/absent/unavailable per repo, no longer `disabled`). The 4-member federation is
   fully live. (Minor: `plainweave --version` = 1.2.0 while `uv tool list` caches v1.1.0 — verb
   works regardless. In warpline's own repo the member reads `unavailable` since warpline isn't a
   plainweave project — expected.)
2. **5th-producer hub handover** — GS-7 oracle wiring + glossary freeze (OD-5). Outward-facing.
   The refreshed warpline-side handover (`docs/integration/2026-06-29-...`, still untracked) is ready.
3. **scan_manifest seam owner-side** (above) — commit the wardline diff, align plainweave, bless the
   contract hub-side; then `weft-9a35aa00e7` / AMBER-2 closes.
4. **Swarm coordination / provenance (owner awareness).** Uncoordinated swarm sessions keep landing
   cross-repo consumer work in shared trees (the `beea0f8` forward-port to `main` reconciled at
   release; the wardline tree co-mingled a doctor/glossary stream with the seam). Worth a
   coordination convention before the next multi-stream push.
5. **(deferred)** Promoting `requirements`/`verification` into the frozen closed envelope vocab —
   future contract/glossary escalation (v1 keeps both as reverify-item fields; PDR-0005/0008).

## What this checkpoint did

- **PDR-0010 — released v1.3.0** (owner-directed): bumped 1.2.0→1.3.0 (`8e5eeea`), merged
  `release/1.2.0`→`main` (`3768794`, `beea0f8` divergence reconciled to empty tree-diff), gate
  green (572 passed), tagged + **pushed** `v1.3.0`, `uv tool install` → live MCP binary 1.3.0,
  and **retired the heddle-venv shadow** (bare `warpline` now 1.3.0).
- **Also this session (sibling/federation, at owner direction):** committed the conformance
  manifest refresh (`18548ca`); refreshed the 5th-producer handover; built the wardline
  `scan_manifest` seam + delta-mode flag; verified two weft interface-gap claims (`scan_manifest`
  real → built it; `verification_events` claim now stale → warpline shipped it); ran a swarm
  reconcile (drift, not damage).
- roadmap.md + metrics.md updated for the release; no reversal trigger crossed.

## Next session starts here

With #1 **resolved** (plainweave reshipped — the requirements member is live, 4-member federation
fully lit), the top pickups are **#2 the 5th-producer hub handover** and **#3 committing the
scan_manifest seam** (closes `weft-9a35aa00e7`). Failing those, the clean repo-local pickups
`warpline-9eae3eb86a` (ungated) or `warpline-17242c627b`.
