# C4 Context

One system box. External actors and systems only.

```mermaid
C4Context
    title Heddle — system context (candidate Weft member; spike scope)

    Person(agent, "AI coding agent", "asks: what changed / what breaks / what must be re-verified")
    Person(operator, "Operator / PM (john)", "dispatches agents; reviews blast radius today by hand")

    System(heddle, "Heddle", "temporal / change-impact authority: per-entity change history + downstream-propagation query")

    System_Ext(git, "Git repository", "the analyzed repo; commits, authors, diffs (read-only + hooks)")
    System_Ext(loomweave, "Loomweave", "structural truth + SEI identity authority (published read surface; OPTIONAL — enrich-only)")
    System_Ext(consumers, "Charter / Legis / Wardline / Filigree", "prospective post-launch consumers of Heddle answers (OPTIONAL — enrich-only, deferred D-01)")

    Rel(agent, heddle, "queries via MCP/CLI")
    Rel(operator, heddle, "queries via CLI")
    Rel(heddle, git, "backfills history; hook-fed incremental ingest")
    Rel(heddle, loomweave, "reads entity catalog + edges at ingest time (when present)")
    Rel(consumers, heddle, "pull affected-set / re-verify answers (post-launch)")
```

Notes:
- Every edge to a sibling is optional by construction (doctrine §5). The only
  hard dependency is git itself.
- Arrows point from the reader to the read surface: Heddle *pulls* from
  Loomweave; consumers *pull* from Heddle. Nothing pushes into a sibling.
