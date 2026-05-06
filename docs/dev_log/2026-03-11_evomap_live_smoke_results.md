## Scope

Follow-up live smoke validation for EvoMap runtime usage after the testing
blueprint landed.

Goal was to validate three concrete chains against the real 18711 runtime:

1. `telemetry ingest -> canonical atom`
2. `issue-domain canonical export -> canonical result`
3. `advisor recall -> evomap source visible`

## Environment Facts

- Active runtime API: `http://127.0.0.1:18711`
- `/v2/cognitive/health` returned `runtime_ready=true`, `graph_ready=true`
- `/v2/advisor/health` reported:
  - `fts_docs=904`
  - `memory.records=652`
- The 18711 service had to be restarted to pick up the issue-family bug fix from
  `893cf70`.

## Smoke 1 — Telemetry ingest -> canonical atom

### Request

`POST /v2/telemetry/ingest` with:

- `event_type = team.run.completed`
- `source = controller_lane_wrapper`
- `agent_name = main`
- `agent_source = codex`
- `role_id = devops`
- `lane_id = verifier`

### Result

Request returned:

```json
{
  "ok": true,
  "trace_id": "smoke-e2-telemetry-trace",
  "recorded": 1,
  "signal_types": ["team.run.completed"]
}
```

Canonical DB delta after restart:

- before: `0`
- after: `1`
- delta: `+1`

Conclusion:

- live telemetry ingestion **does** now reach canonical EvoMap atoms on the
  18711 runtime.

## Smoke 2 — Issue-domain canonical export -> canonical result

### Request

`GET /v1/issues/canonical/export?limit=5`

### Result

Returned successfully with:

- `read_plane = canonical`
- `object_count = 5`
- `projection_counts.graph = 5`
- `projection_counts.ledger_ref = 5`
- `canonical_issue_count = 245`
- `coverage_gap_count = 0`

Conclusion:

- issue-domain canonical export is now live and working on the 18711 runtime.
- The earlier `500` was caused by `match_issue_family()` crashing on list-valued
  metadata; that was fixed in `893cf70`.

## Smoke 3 — Advisor recall -> EvoMap source visible

### Request

`POST /v1/advisor/recall`

```json
{
  "query": "activity team run completed",
  "top_k": 5
}
```

### Result

Returned successfully, but sources were:

```json
{
  "kb": 5,
  "evomap": 0
}
```

### Runtime Interpretation

This is **not** an API failure.

Current live EvoMap data state shows:

- total atoms: `95520`
- `canonical_question = 'activity: team.run.completed'`: present after smoke 1
- atoms satisfying runtime consult visibility gate:
  - `promotion_status in ('active', 'staged')`
  - `groundedness >= 0.5`
  - count: `0`

So the consult helper is behaving as designed:

- EvoMap hits exist in canonical storage
- but none are currently eligible for runtime consult visibility

## Conclusion

Live EvoMap status after this smoke round:

1. `telemetry ingest -> canonical atom`: **PASS**
2. `issue-domain canonical export -> canonical result`: **PASS**
3. `advisor recall -> evomap source visible`: **BLOCKED BY DATA STATE**, not by
   routing or endpoint failure

## Next Most Useful Step

Do **not** change runtime gate semantics yet.

Instead, validate or promote a narrow set of EvoMap atoms so that at least one
real atom satisfies:

- `promotion_status in ('active', 'staged')`
- `groundedness >= 0.5`

Once that exists in the canonical DB, rerun `/v1/advisor/recall` and confirm
`sources.evomap > 0`.
