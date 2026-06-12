# Dogfood Readiness Evidence - 2026-06-13

Command:

```bash
uv run heddle dogfood-eval --output /tmp/heddle-dogfood-results.json --json
```

Result:

- Schema: `heddle.dogfood_results.v1`
- Solo lane: 10/10 cases met parity through MCP `changed -> reverify` in two
  tool calls or fewer.
- Federation lane: 10/10 seeded federation cases showed uplift with enriched
  reverify output.
- Manual escape required: 0/20 cases.
- Output artifact: `/tmp/heddle-dogfood-results.json`

Interpretation:

This satisfies the product-candidate threshold in
`docs/plans/2026-06-13-heddle-1-0-readiness.md`: at least 8/10 solo parity and
at least 8/10 federation uplift. Federation uplift is counted from Heddle-side
implementation plus pre-admission draft specs; sibling repo changes remain
owner-gated.
