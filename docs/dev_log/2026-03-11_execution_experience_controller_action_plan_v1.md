# 2026-03-11 Execution Experience Controller Action Plan v1

## What changed

- added `ops/build_execution_experience_controller_action_plan.py`
- wired `ops/run_execution_experience_review_cycle.py` to emit `controller_action_plan.json`
- covered refresh-only, merge, and validation-failed paths with focused tests

## Why

`controller_packet.json` already gives a single entrypoint, but it still leaves the next controller move implicit. This slice turns the current `recommended_action` into a machine-readable draft plan with:

- action-specific artifact list
- deterministic next steps
- explicit review-plane constraints

It still does not auto-comment or execute anything.

## Output

Each cycle now writes `controller_action_plan.json` with:

- `recommended_action`
- `reason`
- `artifacts`
- `steps`
- `constraints`

## Boundaries

- review-plane only
- draft plan only
- no auto-commenting
- no runtime adoption or active knowledge promotion

## Verification

```bash
PYTHONPATH=. ./.venv/bin/pytest -q \
  tests/test_build_execution_experience_controller_action_plan.py \
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
  ops/build_execution_experience_controller_action_plan.py \
  ops/run_execution_experience_review_cycle.py \
  tests/test_build_execution_experience_controller_action_plan.py \
  tests/test_run_execution_experience_review_cycle.py
```
