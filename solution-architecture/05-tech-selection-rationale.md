# Tech Selection Rationale

> Constraints-first. Several selections are deliberately DEFERRED to the spike —
> recording a premature pick here would be tech-before-problem. Each deferred row
> names what evidence decides it.

| Concern | Selection | Status | Rationale / deciding evidence |
|---|---|---|---|
| Store | SQLite (embedded, WAL) | selected (provisional) | suite norm — filigree and loomweave both run embedded SQLite (`[ASSUMED]` from hub WAL-hygiene work `weft-8e3d02f409`; verify against source); own-use scale fits comfortably; local-first (CON-TEC-03); no shared store permitted anyway (CON-ORG-01). Revisit only if the spike's edge-snapshot volume breaks it. |
| Store placement | outside the analyzed repo's working tree (XDG data dir, per-repo keyed) | selected | NFR-05 / guardrail precedent `weft-d822a7de2d`: an in-repo runtime DB dirties the tree and blocks legis signing. ADR-0004. |
| Ingest trigger | git post-commit hook + cold backfill via `git log` | selected | CON-ORG-04 (hook-fed over discipline-fed); FR-05/FR-06; requires zero member-side code (CON-TEC-02). |
| Graph-edge source | Loomweave published read surface, snapshotted at ingest time | selected (provisional) | doctrine §6: the product that *cares* does the reading; Loomweave stays the structural authority. Exact surface (CLI vs MCP vs DB-read) is spike Q1 — `[ASSUMED]` a sufficient one exists. |
| Solo-mode keying | durable locator: path + qualname, language-aware where cheap | selected | FR-07 / doctrine §5: SEI requires Loomweave; solo mode must not. SEI is an upgrade applied by the identity resolver (ADR-0003). |
| Implementation language | — | DEFERRED to spike | decided by: which language gives the cheapest correct reader for the loomweave surface + git plumbing, and what the spare-capacity devs are fluent in (CON-ORG class). Candidates: Python (suite-common) or Rust (wardline/loomweave plugin line). The spike prototype itself may be either; the prototype's language does not bind the product. |
| Query surface framework | CLI + MCP server, suite-conventional | selected (shape only) | FR-08; agent-first (vision). Specific MCP framework follows the language decision. |
| Graph traversal engine | in-store recursive queries vs in-memory adjacency | DEFERRED to spike | decided by: NFR-01 measurement on the spike corpus at depth ≤ 3. Do not import a graph database — a new store technology would promote the tier to L and violates own-use proportionality. |

## Pre-picked tech rejected / resisted
- **A graph database** (Neo4j etc.): rejected — new store tech for a question
  SQLite adjacency tables likely answer at this scale; would be gold-plating.
- **A daemon/watcher**: rejected for core flows — NFR-03 and doctrine §6 ("if it
  must be running for the suite to work, it violates federation"). A *optional*
  convenience watcher may be revisited post-spike; never required.
- **Member-side emit hooks** ("loomweave pushes change events to heddle"):
  rejected pre-launch outright (CON-TEC-02) and doctrinally suspect at any time
  (load-bearing coupling risk); the read-side design makes it unnecessary —
  that is exactly spike Q1.
