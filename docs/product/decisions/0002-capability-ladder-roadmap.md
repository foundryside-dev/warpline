# PDR-0002 - Capture The Warpline Capability Ladder As Roadmap Backbone

Date: 2026-06-15
Status: accepted
Author: Claude (product owner session)
Owner sign-off: roadmap maintenance is autonomous under the `vision.md` authority
grant ("maintain these product artifacts and append Product Decision Records");
no vision/strategy/authority change is made here.
Supersedes: none
Related: `roadmap.md` (capability ladder + Now/Next/Later), `vision.md`,
`current-state.md`, `~/weft/members/warpline.md`, `~/weft/pm/2026-06-13-warpline-interface-lock.md`

## Context

Warpline was admitted as the 5th Weft member (owner, PDR-0022, 2026-06-14), pulled
into the launch envelope earlier than planned because it closed a gap the release
needed. Its seam *contracts* are frozen; its consumer *implementations* and much of
its diagnostic/predictive value are fast-follow. A live orientation found Warpline
"wobbly" on both integration (inbound seams mostly RESERVED-SHAPE / unimplemented)
and functionality (SEI resolved at ingest only; snapshots never auto-captured; two
of the four reverify enrichment dimensions inert). The product workspace had a
tactical Now/Next/Later roadmap but no durable statement of *where the temporal
authority is going* — so each session risked re-deriving the direction.

## The call

Adopt a five-rung **capability ladder** as the roadmap's directional backbone, and
record `commands.py` decomposition as **Rung 0**:

- **Rung 0** — modularity foundation (split the 959-LOC `commands.py`).
- **Rung 1** — descriptive, made complete & self-healing (SEI re-resolution; auto
  snapshot capture; honesty completion).
- **Rung 2** — diagnostic (co-change graph; verification freshness; light up the
  Wardline/Legis reverify enrichment).
- **Rung 3** — predictive (empirical blast radius; preflight prediction; risk
  trajectory).
- **Rung 4** — temporal fabric (counterfactual queries; ownership drift; fleet-wide
  temporal impact; semantic change typing).

The ladder is intent, not a schedule; horizons map to Now/Next/Later in `roadmap.md`.

## Rationale

The rungs are not a separate backlog from stabilization — they are the same road.
Rung 0/1 *are* the wobble fixes; Rung 2+ are the capabilities only a member with
cross-run history keyed on SEI can own. Capturing them durably keeps the direction
stable across sessions and frames every near-term fix as the first step of the
long-horizon bet, without crossing the authority boundary (no vision, federation
authority-split, admission, or sibling-repo change is decided here).

## Reversal trigger

Reopen this decision if any of the following happens:

- The owner redirects Warpline's domain away from temporal/change-impact.
- A rung's premise is falsified in practice (e.g. the co-change graph proves too
  noisy to be advisory-useful on real repos), in which case that rung is cut or
  reshaped, not silently carried.
- Rung 1 re-resolution + auto-capture do not materially raise SEI-join coverage or
  reduce `NO_SNAPSHOT` answers, indicating the spine problem is mis-diagnosed.
