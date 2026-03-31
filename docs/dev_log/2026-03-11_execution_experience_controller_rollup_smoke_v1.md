# 2026-03-11 Execution Experience Controller Rollup Smoke v1

## Why

The original `controller_surfaces_smoke` was anchored to the first controller
artifact set:

- `controller_packet.json`
- `controller_action_plan.json`
- `review_brief.md`
- `review_reply_draft.md`

Mainline later added two more controller-facing review-plane surfaces:

- `progress_delta.json`
- `controller_update_note.md`

Instead of mutating the older smoke contract and invalidating its existing
fixture bundle, this slice adds a new rollup smoke that includes the full
current controller surface set.

## What Changed

Added `ops/run_execution_experience_controller_rollup_smoke.py`.

It reuses the seeded `controller_surfaces_smoke` run, then extends the emitted
summary with:

- `progress_delta`
- `controller_update_note`
- `progress_signal`

The new summary is written to:

- `controller_rollup_smoke_summary.json`

## Verification

```bash
PYTHONPATH=. ./.venv/bin/pytest -q \
  tests/test_run_execution_experience_controller_rollup_smoke.py

python3 -m py_compile \
  ops/run_execution_experience_controller_rollup_smoke.py \
  tests/test_run_execution_experience_controller_rollup_smoke.py
```

## Boundary

This is review-plane smoke coverage only:

- no runtime adoption
- no active knowledge promotion
- no `TraceEvent` canonical contract change
