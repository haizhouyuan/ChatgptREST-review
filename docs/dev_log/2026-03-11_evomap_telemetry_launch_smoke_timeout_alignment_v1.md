# EvoMap Telemetry Launch Smoke Timeout Alignment v1

Formal launch smoke exposed a tooling mismatch:

- service-side SQLite busy timeout: `30s`
- telemetry smoke HTTP timeout: `20s`

Under transient lock contention, `/v2/telemetry/ingest` still completed with
`200`, but the client timed out before the response arrived.

## Change

Updated `ops/run_evomap_telemetry_live_smoke.py` so launch tooling matches the
runtime it validates:

- `post_telemetry()` now accepts `timeout_seconds`
- default HTTP timeout is `60s`
- activity-atom visibility is checked with bounded polling instead of one
  immediate read
- new CLI flags:
  - `--http-timeout-seconds`
  - `--visibility-timeout-seconds`
  - `--poll-interval-seconds`

## Validation

```bash
PYTHONPATH=. ./.venv/bin/pytest -q \
  tests/test_run_evomap_telemetry_live_smoke.py \
  tests/test_run_evomap_launch_smoke.py \
  tests/test_build_evomap_launch_summary.py

python3 -m py_compile \
  ops/run_evomap_telemetry_live_smoke.py \
  ops/run_evomap_launch_smoke.py \
  tests/test_run_evomap_telemetry_live_smoke.py \
  tests/test_run_evomap_launch_smoke.py \
  tests/test_build_evomap_launch_summary.py
```

This keeps telemetry dedup / visibility validation in the smoke path, but stops
the smoke client from failing earlier than the service it is testing.
