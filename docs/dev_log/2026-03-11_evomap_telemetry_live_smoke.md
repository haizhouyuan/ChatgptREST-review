## Context

We had already closed the archive-vs-live telemetry contract gap in tests, but
the remaining risk was runtime drift: `/v2/telemetry/ingest` might accept an
event while canonical EvoMap still failed to materialize the matching
`activity:*` atom in the live `data/evomap_knowledge.db`.

## What I Added

- Added a repeatable live smoke helper:
  - [`ops/run_evomap_telemetry_live_smoke.py`](/vol1/1000/projects/ChatgptREST/ops/run_evomap_telemetry_live_smoke.py)
- Added focused unit coverage:
  - [`tests/test_evomap_telemetry_live_smoke.py`](/vol1/1000/projects/ChatgptREST/tests/test_evomap_telemetry_live_smoke.py)

The helper:

- posts a unique `team.run.completed` event to `/v2/telemetry/ingest`
- optionally replays the same upstream `event_id`
- queries canonical EvoMap for matching `activity: team.run.completed` atoms
- verifies replay dedup behavior on the live runtime

## Live Validation

Using the API key from the local ChatgptREST env file, the smoke returned:

- `ok=true`
- `recorded=1`
- `signal_types=["team.run.completed"]`

Canonical DB validation then showed a matching atom whose episode metadata
contained:

- `event_id = external-live-20260311-p0`
- `event_type = team.run.completed`
- `agent_name = codex`
- `provider = openai`

That confirms the full live path is now real:

`/v2/telemetry/ingest -> TraceEvent/EventBus -> ActivityIngestService -> canonical EvoMap atom`

I then replayed the same upstream `event_id` twice through the live runtime with
the helper's `--expect-dedup` mode. The results were:

- first POST: `recorded=1`
- second POST: `recorded=0`
- canonical DB: exactly one matching `activity: team.run.completed` atom

That proves the current P0 contract is not only ingesting live telemetry, but
also preserving replay/idempotency on the real stack.

## Why This Matters

This is the first repeatable proof that telemetry P0 is not just test-green but
also runtime-green on the local production stack. It also gives us a reusable
smoke primitive for future replay/idempotency regressions.
