# Heddle Implementation Goal Prompt

```text
Implement Heddle to completion from /home/john/heddle/docs/plans/2026-06-13-heddle-1-0-readiness.md.

Treat the plan as the starting artifact, not as unquestionable truth. First orient in /home/john/heddle and the relevant federation repos: /home/john/weft, /home/john/loomweave, /home/john/filigree, /home/john/wardline, /home/john/legis, and /home/john/charter. Verify current source reality before coding against any sibling interface.

Primary objective:
Deliver Heddle as a local-first, MCP-facing temporal change-impact product that can integrate cleanly into the Weft federation. Heddle must answer what changed, who/when, what downstream entities may be affected, and what should be reverified, while preserving federation authority boundaries. The current product verdict is not-ready; do not promote Heddle until executable evidence proves solo parity and federation uplift.

Priorities:
1. MCP is a first-class product surface, not a wrapper. Every core capability must be available through MCP with structured, agent-friendly responses.
2. Federation integration is a priority. Heddle must consume sibling capabilities only through published surfaces and prepare clean post-admission integration paths.
3. Usability is a hard requirement. If Heddle is harder to use than the current manual/grep-based workflow, the implementation has failed. Deficiencies in the MCP interface are grounds for major refactor, not minor polish.
4. Honest degradation matters. Missing sibling data must produce explicit states like NO_SNAPSHOT, SKIPPED, absent enrichment, stale snapshot, or unknown staleness. Do not invent support that does not exist.
5. Heddle must not become a forbidden aggregator or shared federation store.

Execution loop:
1. Read the plan fully.
2. Validate the next slice against current repo and sibling source reality.
3. If the plan is wrong, stale, under-specified, or risky, update the plan or create a focused design spike before implementing.
4. Implement in small TDD slices.
5. Run the slice's tests and relevant integration checks.
6. Review the slice yourself with a code-review stance: bugs, authority-boundary drift, MCP usability problems, missing tests, stale assumptions.
7. Fix findings before moving on.
8. Repeat until the full plan is implemented, reviewed, and verified.

Risk retirement:
Use additional deep dives, probes, or design spikes whenever needed to retire uncertainty, especially around:
- Loomweave SEI and graph-read surfaces.
- MCP tool shapes, tool naming, response schemas, and agent ergonomics.
- Rev-range semantics and staleness calculation.
- Federation admission boundaries and sibling-owned integration work.
- Hook-fed ingest reliability and repo cleanliness.
- Whether Heddle is actually easier and more useful than current workflows.

MCP requirements:
- MCP tools must be discoverable, documented through tools/list, stable, and easy for agents to call.
- MCP responses must be structured JSON with clear schema/version, query metadata, enrichment state, warnings, and actionable next steps where appropriate.
- MCP failures must be structured and recoverable.
- Do not defer MCP quality until the end. If CLI and MCP diverge, refactor shared handlers.
- Include MCP-focused tests for every user-facing capability.
- Perform at least one end-to-end MCP usability review before completion.

Federation requirements:
- Treat Loomweave as structure/identity authority and SEI owner.
- Treat Filigree as work-state authority.
- Treat Wardline as trust/finding authority.
- Treat Legis as governance/git/CI authority.
- Treat Charter as obligation/requirements authority.
- Heddle owns temporal change-impact facts only.
- Do not patch sibling repos as part of Heddle implementation unless explicitly authorized after owner admission.
- Draft integration contracts and consumer tickets must stay Heddle-owned and pre-admission until explicitly accepted.

Implementation expectations:
- Follow the repo's plan tasks, but correct the plan when implementation reality proves it wrong.
- Keep code simple, local-first, and dependency-light unless a real need appears.
- Use SQLite safely and keep Heddle state outside analyzed repos.
- Preserve clean git behavior and fail-soft hooks.
- Add tests proportional to risk, with strong coverage around MCP, staleness, rev ranges, degraded states, and federation boundaries.
- Use subagents for independent review/deep-dive work where useful, especially before major integration or MCP interface decisions.

Completion criteria:
- All planned tasks are implemented or explicitly superseded by a documented better approach.
- Unit, integration, spike, MCP, lint, type, release-candidate, and member-boundary gates pass or skip only with explicit justified reasons.
- spike/REPORT.md, dogfood results, and measurement evidence exist and support the productization decision.
- The MCP interface has been reviewed as a primary product interface and refactored if awkward.
- Federation integration artifacts are prepared without unauthorized sibling repo changes.
- Requirement traceability is current and executable.
- The final state is clean, documented, and usable by an agent without hidden manual steps.

Do not stop at partial implementation. Continue through plan, implement, review, fix, and verify loops until Heddle is genuinely ready as a product candidate or until a documented no-go/park decision is reached from evidence.
```
