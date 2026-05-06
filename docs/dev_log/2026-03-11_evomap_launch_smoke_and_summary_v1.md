# EvoMap Launch Smoke And Summary v1

This slice closes the last operator-facing gaps before a narrow EvoMap go-live.

Added:

- `ops/run_evomap_launch_smoke.py`
- `ops/build_evomap_launch_summary.py`
- `tests/test_run_evomap_launch_smoke.py`
- `tests/test_build_evomap_launch_summary.py`

## What changed

### 1. Launch smoke became a tracked artifact

`ops/run_evomap_launch_smoke.py` now writes a real artifact directory under:

- `artifacts/monitor/evomap_launch_smoke/<timestamp>/launch_smoke.json`

The smoke covers three pre-launch chains:

1. issue-domain canonical export
2. planning reviewed runtime-pack opt-in recall
3. telemetry live ingest into canonical EvoMap

The default launch-smoke profile uses a single telemetry replay. Dedup checks
stay available, but they are not part of the default pre-launch availability
gate.

The smoke executes telemetry first, then the read-plane checks. That keeps the
most write-sensitive chain away from later recall-side bookkeeping on the same
runtime.

### 2. Operator summary became a first-class report

`ops/build_evomap_launch_summary.py` now writes:

- `launch_summary.json`
- `launch_summary.md`

The summary reports:

- runtime health
- canonical DB totals and source/promotion breakdowns
- latest approved planning runtime-pack release bundle
- issue-domain canonical-export status
- latest launch-smoke result
- launch flags
- rollback instructions

### 3. Regression coverage

Added focused tests for:

- launch-smoke orchestration and artifact persistence
- launch-summary DB aggregation and output rendering

## Validation

```bash
PYTHONPATH=. ./.venv/bin/pytest -q \
  tests/test_run_evomap_launch_smoke.py \
  tests/test_build_evomap_launch_summary.py

python3 -m py_compile \
  ops/run_evomap_launch_smoke.py \
  ops/build_evomap_launch_summary.py \
  tests/test_run_evomap_launch_smoke.py \
  tests/test_build_evomap_launch_summary.py
```

## Why this matters

The codebase already had the core EvoMap substrate and the explicit planning
runtime-pack hook. The remaining P0 gap was operational: one smoke script to
prove the intended launch scope, and one summary artifact to show operators what
is live, what is opt-in, and how to roll back cleanly.
