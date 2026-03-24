# 2026-03-11 Archive Envelope Live Smoke

## Objective

Validate the posthoc/archive telemetry path on the real runtime, not just in unit tests.

This round targeted the existing `openmind-v3-agent-ops-v1` archive envelope shape for:

- `agent.task.closeout`
- `agent.git.commit`

The goal was to prove that archive-style agent activity events can traverse:

`/v2/telemetry/ingest -> TraceEvent/EventBus -> ActivityIngestService -> canonical EvoMap`

without introducing a second live event system.

## What Was Added

- [`ops/run_evomap_archive_envelope_live_smoke.py`](/vol1/1000/projects/ChatgptREST/ops/run_evomap_archive_envelope_live_smoke.py)
- [`tests/test_evomap_archive_envelope_live_smoke.py`](/vol1/1000/projects/ChatgptREST/tests/test_evomap_archive_envelope_live_smoke.py)

The smoke helper sends a closeout event and a commit event in archive-envelope form to the live
18711 runtime, then checks canonical `data/evomap_knowledge.db` for:

- `task result: <task_ref> by codex`
- `commit <sha8> in ChatgptREST`

## Validation

```bash
./.venv/bin/pytest -q \
  tests/test_evomap_archive_envelope_live_smoke.py \
  tests/test_activity_ingest.py \
  tests/test_telemetry_contract.py

set -a
source ~/.config/chatgptrest/chatgptrest.env 2>/dev/null || true
source /vol1/maint/MAIN/secrets/credentials.env 2>/dev/null || true
set +a

./.venv/bin/python ops/run_evomap_archive_envelope_live_smoke.py \
  --report-json artifacts/evomap_smoke/<ts>_archive_envelope_live_smoke.json
```

Live result:

- `response.ok = true`
- `response.recorded = 2`
- `signal_types = ['agent.task.closeout', 'agent.git.commit']`
- canonical DB counts moved:
  - `closeout_count: 0 -> 1`
  - `commit_count: 0 -> 1`

## Conclusion

The archive/posthoc envelope path is now validated on the real runtime for two concrete event
classes:

- `agent.task.closeout`
- `agent.git.commit`

So the current `#114` state is:

- live helper emitter path: proven
- `controller_lane_wrapper` emitter path: proven
- OpenClaw telemetry plugin emitter path: proven
- archive envelope path for closeout/commit: proven
