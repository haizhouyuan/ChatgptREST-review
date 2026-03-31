# 2026-03-11 Execution Experience Controller Surfaces Smoke v1

## What changed

- added `ops/run_execution_experience_controller_surfaces_smoke.py`
- added a focused smoke test for seeded end-to-end materialization of controller-facing review artifacts

## Why

The execution review-plane now emits a controller chain:

- `controller_packet.json`
- `controller_action_plan.json`
- `review_brief.md`
- `review_reply_draft.md`

This slice turns the ad-hoc seeded verification into a reusable smoke entrypoint so controller/release validation can confirm the whole chain still materializes together.

## Output

The smoke writes `controller_surfaces_smoke_summary.json` with:

- `mode`
- `recommended_action`
- `reason`
- key artifact paths for packet / action plan / brief / draft

## Boundaries

- review-plane validation only
- seeded local smoke only
- no runtime adoption
- no live retrieval or promotion changes

## Verification

```bash
PYTHONPATH=. ./.venv/bin/pytest -q \
  tests/test_run_execution_experience_controller_surfaces_smoke.py \
  tests/test_build_execution_experience_controller_action_plan.py \
  tests/test_build_execution_experience_controller_packet.py \
  tests/test_build_execution_experience_review_reply_draft.py \
  tests/test_render_execution_experience_review_brief.py \
  tests/test_build_execution_experience_attention_manifest.py \
  tests/test_build_execution_experience_governance_snapshot.py \
  tests/test_run_execution_experience_review_cycle.py

PYTHONPATH=. ./.venv/bin/python -m py_compile \
  ops/run_execution_experience_controller_surfaces_smoke.py \
  tests/test_run_execution_experience_controller_surfaces_smoke.py
```
