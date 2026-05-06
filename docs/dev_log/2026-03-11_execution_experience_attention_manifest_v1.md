# 2026-03-11 Execution Experience Attention Manifest v1

## What changed

- added `ops/build_execution_experience_attention_manifest.py`
- wired `ops/run_execution_experience_review_cycle.py` to emit `attention_manifest.json`
- covered refresh-only, merge, and validation-failed paths with focused tests

## Why

`governance_snapshot.json` gives stable counts and flags, but controller still had to jump between separate artifact files to find the concrete queue or follow-up bundle to inspect next. This slice adds a small route manifest that keeps execution experience governance inside review-plane while reducing file discovery work.

## Output

Each cycle now writes `attention_manifest.json` with:

- review pack and reviewer-output entry points
- backlog summary and decision scaffold paths
- validation-summary path and reviewer gaps when present
- governance queue file routes
- follow-up branch routes for `accept / revise / defer / reject`

## Boundaries

- review-plane only
- no runtime adoption
- no active knowledge promotion
- no live contract changes

## Verification

```bash
PYTHONPATH=. ./.venv/bin/pytest -q \
  tests/test_build_execution_experience_attention_manifest.py \
  tests/test_build_execution_experience_governance_snapshot.py \
  tests/test_run_execution_experience_review_cycle.py \
  tests/test_build_execution_experience_followup_manifest.py \
  tests/test_build_execution_experience_rejected_archive_queue.py \
  tests/test_build_execution_experience_deferred_revisit_queue.py \
  tests/test_export_execution_experience_acceptance_pack.py \
  tests/test_build_execution_experience_revision_worklist.py

PYTHONPATH=. ./.venv/bin/python -m py_compile \
  ops/build_execution_experience_attention_manifest.py \
  ops/run_execution_experience_review_cycle.py \
  tests/test_build_execution_experience_attention_manifest.py \
  tests/test_run_execution_experience_review_cycle.py
```
