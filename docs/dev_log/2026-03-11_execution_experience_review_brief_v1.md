# 2026-03-11 Execution Experience Review Brief v1

## What changed

- added `ops/render_execution_experience_review_brief.py`
- wired `ops/run_execution_experience_review_cycle.py` to emit `review_brief.md`
- covered refresh-only, merge, and validation-failed paths with focused tests

## Why

The cycle now emits stable machine-readable governance artifacts, but controller still benefits from one human-readable surface that can be opened directly in a pane or issue reply workflow. This slice adds a markdown brief that renders the most important review-plane counters, flags, and artifact routes without changing any decision logic.

## Output

Each cycle now writes `review_brief.md` with:

- totals for candidate coverage and follow-up load
- validation availability and reviewer gaps
- governance state/action counts
- follow-up branch counts
- key route paths for review pack, backlog, validation, queues, and reviewer manifest

## Boundaries

- review-plane only
- no runtime adoption
- no active knowledge promotion
- no live event or retrieval-default changes

## Verification

```bash
PYTHONPATH=. ./.venv/bin/pytest -q \
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
  ops/render_execution_experience_review_brief.py \
  ops/run_execution_experience_review_cycle.py \
  tests/test_render_execution_experience_review_brief.py \
  tests/test_run_execution_experience_review_cycle.py
```
