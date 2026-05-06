# 2026-03-11 Execution Experience Review Reply Draft v1

## What changed

- added `ops/build_execution_experience_review_reply_draft.py`
- wired `ops/run_execution_experience_review_cycle.py` to emit `review_reply_draft.md`
- covered refresh-only, merge, and validation-failed paths with focused tests

## Why

The cycle now emits machine-readable manifests plus a human-readable brief, but controller still needs a deterministic way to decide what kind of review-plane action comes next. This slice adds a draft-only reply artifact that turns existing flags into a narrow recommendation without posting anything automatically.

## Recommendation order

The draft keeps the logic deterministic and review-plane scoped:

1. `fix_review_outputs`
2. `collect_missing_reviews`
3. `continue_review`
4. `route_followups`
5. `park`

## Boundaries

- draft only, no auto-commenting
- review-plane only
- no runtime adoption
- no active knowledge promotion

## Verification

```bash
PYTHONPATH=. ./.venv/bin/pytest -q \
  tests/test_build_execution_experience_review_reply_draft.py \
  tests/test_render_execution_experience_review_brief.py \
  tests/test_build_execution_experience_attention_manifest.py \
  tests/test_build_execution_experience_governance_snapshot.py \
  tests/test_run_execution_experience_review_cycle.py \
  tests/test_build_execution_experience_followup_manifest.py \
  tests/test_build_execution_experience_rejected_archive_queue.py \
  tests/test_build_execution_experience_deferred_revisit_queue.py \
  tests/test_export_execution_experience_acceptance_pack.py \
  tests/test_build_execution_experience_revision_worklist.py

PYTHONPATH=. ./.venv/bin/python -m py_compile \
  ops/build_execution_experience_review_reply_draft.py \
  ops/run_execution_experience_review_cycle.py \
  tests/test_build_execution_experience_review_reply_draft.py \
  tests/test_run_execution_experience_review_cycle.py
```
