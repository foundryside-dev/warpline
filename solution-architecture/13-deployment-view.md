# Deployment View

Own-use, local-first; this page is deliberately small.

- **Environments:** developer workstation only (Linux first — the operator's
  environment). No staging/prod distinction; no cloud (CON-TEC-03).
- **Runtime topology:** no resident process. CLI invoked by user, scripts, and
  the git post-commit hook; MCP server spawned per agent session over stdio
  (suite convention). Core flows never require anything to be "up"
  (doctrine §6 test).
- **Install:** single tool install (mechanism mirrors siblings — e.g. `uv tool
  install` if Python is selected in `05-`). Per-repo activation = `heddle init`
  (installs the hook, registers the store). NOTE the installed-vs-source drift
  lesson (three source-fixed ≠ live-fixed incidents in the suite): the spike
  prototype runs from source; any installed build must carry a version probe.
- **Data:** one SQLite DB per analyzed repo under the user data dir
  (XDG `$XDG_DATA_HOME/heddle/<repo-fingerprint>/`), never inside the analyzed
  repo's working tree (NFR-05, ADR-0004). Backup = file copy; loss = re-derivable
  by backfill + re-snapshot (nothing here is the system of record for anything
  a sibling owns; git is the recovery source).
- **Scaling posture:** single user, repos ≤ ~200k LOC / ~20k commits (NFR
  envelope). No horizontal anything.
- **Network boundaries:** none in core flows; 100% offline-capable (NFR-03).
  Cross-host is descoped (D-05).
