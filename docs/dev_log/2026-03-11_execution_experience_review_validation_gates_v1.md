---
title: Execution Experience Review Validation Gates
version: v1
updated: 2026-03-11
status: completed
---

# Goal

Turn execution experience review validation from passive reporting into an
optional fail-fast maintenance gate.

The cycle already emitted:

- `review_backlog_summary.json`
- `review_output_validation_summary.json`

but it would still continue merging reviewer outputs even when a caller wanted a
strict maintenance run.

# Changed

- `ops/run_execution_experience_review_cycle.py`
- `tests/test_run_execution_experience_review_cycle.py`

# What Changed

## 1. Added optional strict review gates

`run_execution_experience_review_cycle.py` now supports:

- `--require-valid-reviews`
- `--require-complete-reviews`

They only apply when `--review-json` inputs are provided.

## 2. Validation failure now writes a terminal review-plane summary

If a required gate fails, the cycle now:

- writes `review_output_validation_summary.json`
- writes `cycle_summary.json` with:
  - `ok = false`
  - `mode = validation_failed`
  - `validation_errors = [...]`
- raises `RuntimeError`

That preserves artifacts for debugging instead of silently failing before any
state is visible.

## 3. Completeness and structural validity stay separate

The gates intentionally remain independent:

- `require_valid_reviews` checks structural correctness
- `require_complete_reviews` checks whether all expected reviewer lanes replied

This keeps partial-but-clean review rounds usable when the caller wants them,
while still allowing strict maintenance callers to fail fast.

# Boundary

This round does **not**:

- modify the live `TraceEvent` contract
- alter runtime retrieval defaults
- promote reviewed experiences into active knowledge
- create a second live event standard
- introduce reviewer orchestration

# Verification

Focused tests:

```bash
PYTHONPATH=. ./.venv/bin/pytest -q \
  tests/test_run_execution_experience_review_cycle.py \
  tests/test_validate_execution_experience_review_outputs.py \
  tests/test_report_execution_experience_review_backlog.py \
  tests/test_merge_execution_experience_review_outputs.py \
  tests/test_build_execution_experience_review_pack.py \
  tests/test_compose_execution_experience_review_decisions.py
```

Added regression coverage for:

- incomplete reviewer coverage + `require_complete_reviews=True`
- invalid reviewer decision value + `require_valid_reviews=True`

In both cases the cycle writes `mode=validation_failed` before raising.
