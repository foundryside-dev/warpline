# C4 Containers

One page. Technology labels per container (provisional where `05-` defers).

```mermaid
C4Container
    title Heddle — containers

    Person(agent, "AI coding agent")

    System_Boundary(heddle, "Heddle (single local install; no daemon)") {
        Container(cli, "heddle CLI", "language TBD (05-)", "human + script surface; also the hook entrypoint")
        Container(mcp, "heddle MCP server", "MCP over stdio", "agent-first query surface; same core library as the CLI")
        Container(core, "core library", "language TBD (05-)", "ingest, identity resolution, snapshot diffing, propagation engine")
        ContainerDb(store, "temporal store", "SQLite (WAL)", "change events, edge snapshots, entity key map — OUTSIDE the analyzed repo tree (XDG data dir)")
    }

    System_Ext(git, "Git repo", "read-only + post-commit hook")
    System_Ext(loomweave, "Loomweave read surface", "optional")

    Rel(agent, mcp, "MCP tools")
    Rel(agent, cli, "shell")
    Rel(cli, core, "calls")
    Rel(mcp, core, "calls")
    Rel(core, store, "reads/writes")
    Rel(core, git, "git plumbing (log, diff)")
    Rel(core, loomweave, "catalog/edge read at ingest (when present)")
```

- No long-running process: the MCP server runs per-session like sibling tools;
  the CLI is invoked by the git hook. (NFR-03; doctrine §6.)
- One store per analyzed repo, keyed by repo identity, never inside the repo
  working tree (NFR-05, ADR-0004).
