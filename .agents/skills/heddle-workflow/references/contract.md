# Heddle frozen contract (reference)

Authoritative source: `/home/john/weft/pm/2026-06-13-heddle-interface-lock.md`
(FROZEN). heddle implements TO this contract; it is never edited locally.

## Success envelope (every outbound tool)

```json
{
  "schema": "heddle.<contract>.v1",
  "ok": true,
  "query": {"repo": "...", "tool": "...", "arguments": {}, "filters": {},
            "sort": {"by": "...", "order": "asc"}, "page": {"limit": 50, "cursor": null}},
  "data": {},
  "warnings": [],
  "next_actions": {},
  "enrichment": {"sei": "...", "edges": "...", "work": "...", "risk": "...",
                  "governance": "...", "requirements": "..."},
  "meta": {"producer": {"tool": "heddle", "version": "..."},
            "local_only": true, "peer_side_effects": []}
}
```

- `enrichment` CLOSED vocab: `present | absent | unavailable` (plus
  `stale | partial | skipped` for `edges`). `absent` = peer present, no fact;
  `unavailable` = peer unreachable. Neither is ever a transport error or an
  implied clean/allowed state.

## Error envelope (`heddle.error.v1`)

```json
{"code": -32602, "message": "invalid params",
 "data": {"schema": "heddle.error.v1", "error_code": "...", "rejected_field": "...",
          "retryability": "retry_safe|retry_with_changes|fatal", "hint": "...", "details": {}}}
```

CLOSED `error_code` set: `missing_required_field, invalid_repo, invalid_rev_range,
invalid_entity_ref, invalid_changed_refs, invalid_depth, invalid_filter,
invalid_sort, peer_unavailable, snapshot_unavailable, internal_error`. Switch on
`error_code`, not message text.

## Keying

Every entity carries BOTH `locator` and `sei` (`loomweave:eid:<32-hex>`, opaque —
heddle never mints or parses it). `heddle_entity_key_id` is heddle-internal and
NOT a federation key; key on `sei` (preferred) or `locator`.

## Seam boundaries (deconfliction-first; advisory never gates)

- loomweave owns current structure + SEI minting/resolution.
- filigree owns work state; heddle reads links, never files/closes/claims.
- wardline owns trust policy; heddle re-derives risk as ordering signal, never a
  clean/allow verdict. wardline absent → `risk: unavailable`, never `clean`.
- legis owns governance + the rename feed; heddle emits advisory impact only.
