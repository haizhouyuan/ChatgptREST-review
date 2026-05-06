# 2026-03-11 Execution Experience Progress Delta Cycle Integration v1

## Why

`ops/build_execution_experience_progress_delta.py` already gave controller a
stable way to compare two execution experience review checkpoints, but it still
sat outside the main cycle.

That meant:

- controller had to call the builder separately
- `cycle_summary.json` did not carry the cross-cycle governance comparison
- validation-failed runs and merge runs had no first-class progress artifact

## What Changed

Integrated progress-delta emission into
`ops/run_execution_experience_review_cycle.py`.

When a previous cycle directory already exists and contains both:

- `governance_snapshot.json`
- `controller_action_plan.json`

the new cycle now also writes:

- `progress_delta.json`

and surfaces it in the cycle payload as:

- `progress_delta`
- `progress_delta_path`

This works for:

- refresh-only cycles after an earlier baseline exists
- validation-failed cycles
- refresh-merge cycles

On the very first cycle, the fields stay empty:

- `progress_delta = null`
- `progress_delta_path = ""`

## Verification

```bash
PYTHONPATH=. ./.venv/bin/pytest -q \
  tests/test_run_execution_experience_review_cycle.py \
  tests/test_build_execution_experience_progress_delta.py

python3 -m py_compile \
  ops/run_execution_experience_review_cycle.py \
  ops/build_execution_experience_progress_delta.py \
  tests/test_run_execution_experience_review_cycle.py \
  tests/test_build_execution_experience_progress_delta.py
```

## Outcome

The execution experience review cycle now materializes a cross-cycle governance
delta as part of the normal review-plane maintenance run, without touching
runtime adoption or active knowledge promotion.
