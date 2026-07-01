# PDR-0011 - 5th-Producer Conformance Obligation Discharged (handover delivered to the weft hub)

Date: 2026-07-01
Status: accepted
Owner sign-off: the **delivery to the weft hub was the owner's outward act**, executed
2026-07-01 ("I've handed over to weft; close the obligation from our side"). This PDR records
the discharge of warpline's side; the remaining GS-7 wiring + glossary freeze are the hub's
obligation, not warpline's.
Supersedes: none
Related: admission (PDR-0022) + OD-5 (`weft/pm/2026-06-13-warpline-interface-lock.md` §8);
the finalized handover `docs/integration/2026-07-01-warpline-5th-producer-handover.md`;
PDR-0010 (v1.3.0 — the surface delivered).

## Context

On admission (2026-06-13, PDR-0022) warpline took on the **OD-5** obligation: contribute its
golden-vector conformance package to the four-member GS-7 oracle as the **5th producer**. That
warpline-side deliverable — the handover package (19 golden vectors, 7 frozen MCP tools, the
frozen envelope/error/reason contracts, the consumed-sibling map, and the glossary-freeze
attestation checklist), current to the released **v1.3.0** / fully-live four-member state — was
finalized and committed this session, then **delivered to the weft hub by the owner**.

## The call

**Discharge warpline's side of the 5th-producer conformance obligation.** The package is
delivered; warpline's conformance-delivery duty (OD-5) is complete. The remaining acts —
wiring warpline into the GS-7 oracle and turning the gate on, signing the glossary freeze, and
deciding whether the 3 consumed-contract goldens (legis/wardline/plainweave) join the GS-7
fixture set — are now the **hub's**, per the authority boundary (GS-7 inclusion + the freeze are
the hub owner's act, outside warpline's repo-local grant). This closes escalation #2 on the
warpline side and removes it from `current-state.md`.

## Rationale

The package is complete, current to the shipped surface, and self-consistent (verified this
session: 19 vectors green, 7 tools, the requirements member live). Delivery discharges the
obligation; keeping it open on warpline's side would misattribute the hub's remaining acts as
warpline debt. The document itself flags done-vs-owner cleanly, so the hub inherits an accurate
package.

## Reversal trigger

Reopen if the hub **returns the package for changes** — a conformance gap (a warpline vector
fails in the GS-7 harness), a frozen-contract issue surfaced during wiring, or a glossary-freeze
objection. Any such bounce means the warpline-side package was incomplete and the obligation
reopens for a fix. Tie to `metrics.md`: a GS-7 oracle failure attributed to warpline's vectors,
or the hub reporting the 5th-producer registration blocked on a warpline-side defect.
