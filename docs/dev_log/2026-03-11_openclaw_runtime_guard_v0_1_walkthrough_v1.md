# 2026-03-11 OpenClaw Runtime Guard v0.1 Walkthrough v1

## Goal

Implement `#120` as Phase 0 + Phase 1 only:

- observe-first sidecar
- first six deterministic detectors
- artifact bundle + digest
- smoke + systemd

## What Changed

Added:

- `ops/openclaw_runtime_guard.py`
- `ops/run_openclaw_runtime_guard_smoke.py`
- `tests/test_openclaw_runtime_guard.py`
- `tests/test_openclaw_runtime_guard_smoke.py`
- `ops/systemd/chatgptrest-openclaw-runtime-guard.service`
- `ops/systemd/chatgptrest-openclaw-runtime-guard.timer`
- `docs/ops/2026-03-11_openclaw_runtime_guard_v0_1_v1.md`

## Design Notes

The sidecar is timer-driven and scans durable state instead of introducing a
second long-running subscriber process.

Input planes:

- EventBus SQLite for live canonical telemetry
- controller lane SQLite for lane heartbeat state
- EvoMap knowledge SQLite for runtime visibility
- optional read-only `/v1/advisor/recall` probe for planning opt-in

This keeps the guard outside the control plane:

- no new event schema
- no mutation of runtime knowledge
- no hidden auto-repair

## Detector Contract

Current detector families:

1. lane/event heartbeat stale
2. started workflow missing terminal event after SLA
3. tool failure ratio spike
4. execution telemetry contract violations
5. planning opt-in activated but explicit probe returns zero hit
6. EvoMap runtime-visible atom/source floor regression

Artifacts:

- `state_summary.json`
- `incident_summary.json`
- `detector_hits.json`
- `runtime_guard_latest.md`

## Validation

Focused checks:

```bash
cd /vol1/1000/projects/ChatgptREST/.worktrees/issue-120-runtime-guard
python3 -m py_compile \
  ops/openclaw_runtime_guard.py \
  ops/run_openclaw_runtime_guard_smoke.py \
  tests/test_openclaw_runtime_guard.py \
  tests/test_openclaw_runtime_guard_smoke.py

PYTHONPATH=. /vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q \
  tests/test_openclaw_runtime_guard.py \
  tests/test_openclaw_runtime_guard_smoke.py
```

Synthetic smoke:

```bash
cd /vol1/1000/projects/ChatgptREST/.worktrees/issue-120-runtime-guard
PYTHONPATH=. /vol1/1000/projects/ChatgptREST/.venv/bin/python \
  ops/run_openclaw_runtime_guard_smoke.py \
  --output-dir /tmp/runtime-guard-smoke
```

## Deferred

Not included in this PR:

- Issue Ledger auto-report hooks
- Feishu notification hook
- auto-actions / self-heal
- extra detector families beyond the first six
