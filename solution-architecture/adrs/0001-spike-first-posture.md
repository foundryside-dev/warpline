# ADR-0001 — Spike-first posture: this package designs to a go/no-go, not a build

**Status:** Accepted · 2026-06-10
**Context:** PDR-0013 (weft) ranks Heddle as discovery slot #1 with a standing
agentic-first admission bar; doctrine §7 reserves member admission to the owner;
the owner directed (2026-06-10) that spare capacity explore future systems while
the four launch members stay frozen. Naive Heddle framing is a forbidden
aggregator (doctrine §6) — the concept's own source names this as the reason it
is a spike.

**Decision:** All work in this workspace targets the go/no-go spike
(`weft-e4589e6570`). The artifact set is initialized at tier M but the `99-`
assembly + consistency gate are deferred until spike questions Q1–Q4
(`spike/SPIKE-BRIEF.md`) resolve. A "go" produces an admission
*recommendation* to the owner; "no-go" archives this repo with the evidence.

**Alternatives considered:**
- *Design-complete then build* — rejected: front-loads decisions the spike
  exists to test; repeats tech-before-problem.
- *Just prototype, no artifact set* — rejected: the doctrinal questions (§5/§6
  boundaries, Charter seam) are design questions a prototype alone won't
  answer; and the admission case needs citable artifacts.

**Consequences:** several `05-` selections stay DEFERRED; wire shapes stay
unfrozen (`11-`); anyone treating this repo as a committed member is wrong by
construction.

**Rollback / expiry:** superseded automatically by the owner's §7 ruling,
either direction. Re-examine if the spike has not run within 60 days
(by 2026-08-09) — stale spikes rot into assumed commitments.
