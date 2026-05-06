# 2026-03-11 OpenClaw Telemetry Plugin Live Smoke Alignment

## Objective

Tighten the live smoke for `openmind-telemetry` so it proves **this run's** OpenClaw plugin
events were materialized into canonical EvoMap, instead of accidentally matching older atoms.

## Root Cause

The first live smoke proved the plugin path was active, but the correlation logic was too
optimistic:

- the script assumed the CLI `--session-id` would be the same identity used by the plugin
- in practice the OpenClaw runtime exposed multiple session identities in the result payload:
  - requested CLI session id
  - `agentMeta.sessionId`
  - `systemPromptReport.sessionId`
  - `systemPromptReport.sessionKey`
- canonical EvoMap rows were appearing under a real runtime session id
  (`systemPromptReport.sessionId` in the successful path), not the requested CLI session id

This meant the old smoke script could miss the rows and report `coverage_ok=false` even though
the plugin had already emitted valid `team.run.created` / `workflow.completed` events.

## Fix

Updated [`ops/run_openclaw_telemetry_plugin_live_smoke.py`](/vol1/1000/projects/ChatgptREST/ops/run_openclaw_telemetry_plugin_live_smoke.py):

- collect multiple observed session candidates from the OpenClaw JSON result:
  - requested session id
  - `agentMeta.sessionId`
  - `systemPromptReport.sessionId`
  - `systemPromptReport.sessionKey`
- derive multiple `task_ref` candidates from those session ids
- add a canonical DB watermark (`before_rowid`) and only match atoms with `rowid > before_rowid`

This converts the smoke from:

- "can I find any historical OpenClaw activity atom with a similar task ref?"

to:

- "did this run create fresh `team.run.created` + terminal `workflow.*` atoms in canonical EvoMap?"

## Validation

```bash
./.venv/bin/pytest -q \
  tests/test_openclaw_telemetry_plugin_live_smoke.py \
  tests/test_openclaw_cognitive_plugins.py \
  tests/test_rebuild_openclaw_openmind_stack.py \
  tests/test_activity_ingest.py \
  tests/test_telemetry_contract.py

./.venv/bin/python ops/run_openclaw_telemetry_plugin_live_smoke.py \
  --report-json artifacts/evomap_smoke/20260311T*.json
```

Result of the aligned live smoke:

- `ok = true`
- `coverage_ok = true`
- `after_match_count = 2`
- matched atoms were both new rows after the watermark:
  - `activity: team.run.created`
  - `activity: workflow.completed`

The LLM answer still did not follow the exact `OPENCLAW_TELEMETRY_OK ...` token instruction, so
`agent_run_ok=false`, but that is now correctly treated as separate from telemetry coverage.

## Conclusion

OpenClaw `openmind-telemetry` plugin coverage into canonical EvoMap is now demonstrated with a
fresh-row live smoke, not inferred from historical atoms.
