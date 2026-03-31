# 2026-03-11 Execution Experience Progress Delta v1

## Why

The execution experience review plane already had single-cycle controller surfaces:

- `governance_snapshot.json`
- `controller_packet.json`
- `controller_action_plan.json`
- `review_brief.md`
- `review_reply_draft.md`

What it still lacked was a small controller-facing comparison surface between two
cycles. Without that, controller could see the current backlog and recommended
action, but not whether the review plane was actually improving, regressing, or
just churning.

## What Changed

Added `ops/build_execution_experience_progress_delta.py`.

It compares two cycle checkpoints:

- previous `governance_snapshot.json`
- current `governance_snapshot.json`
- previous `controller_action_plan.json`
- current `controller_action_plan.json`

and emits one `progress_delta.json` with:

- totals deltas (`reviewed_candidates`, `backlog_candidates`, `followup_candidates`, ...)
- review-state deltas
- validation-state deltas
- queue deltas (`by_state`, `by_action`, `followup_by_branch`)
- attention-flag flips
- controller action change and severity delta
- one coarse `progress_signal`: `improved`, `regressed`, `mixed`, or `unchanged`

## Verification

```bash
PYTHONPATH=. ./.venv/bin/pytest -q tests/test_build_execution_experience_progress_delta.py
python3 -m py_compile \
  ops/build_execution_experience_progress_delta.py \
  tests/test_build_execution_experience_progress_delta.py
```

## Boundary

This stays inside candidate/review-plane governance:

- no runtime adoption
- no active knowledge promotion
- no retrieval-default change
- no `TraceEvent` contract change
