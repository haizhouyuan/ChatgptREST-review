# 2026-03-11 Execution Experience Controller Packet v1

## What changed

- added `ops/build_execution_experience_controller_packet.py`
- wired `ops/run_execution_experience_review_cycle.py` to emit `controller_packet.json`
- covered refresh-only, merge, and validation-failed paths with focused tests

## Why

The cycle now emits several controller-facing artifacts:

- `governance_snapshot.json`
- `attention_manifest.json`
- `review_brief.md`
- `review_reply_draft.md`

This slice gives controller one stable JSON entrypoint that points at those artifacts and repeats the minimum summary needed for fast routing.

## Output

Each cycle now writes `controller_packet.json` with:

- recommended action and reason
- headline counts for candidates, backlog, follow-up, validation availability
- artifact paths for snapshot / manifest / brief / reply draft
- attention flags
- follow-up branch payload from `attention_manifest`

## Boundaries

- review-plane only
- controller-facing packet only
- no auto-commenting
- no runtime adoption or active knowledge promotion

## Verification

```bash
PYTHONPATH=. ./.venv/bin/pytest -q \
  tests/test_build_execution_experience_controller_packet.py \
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
  ops/build_execution_experience_controller_packet.py \
  ops/run_execution_experience_review_cycle.py \
  tests/test_build_execution_experience_controller_packet.py \
  tests/test_run_execution_experience_review_cycle.py
```
