# 2026-03-11 Execution Experience Governance-Queue Fixture Bundle Walkthrough v1

## Purpose

This walkthrough explains how the tracked governance-queue fixture bundle maps
onto mainline's new controller-facing governance queue export surface.

## Files and roles

- [experience_candidates_v1.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/execution_experience_governance_queue_fixture_bundle_20260311/experience_candidates_v1.json)
  mirrors the candidate universe used by the preceding scaffold bundle
- [reviewer_manifest_v1.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/execution_experience_governance_queue_fixture_bundle_20260311/reviewer_manifest_v1.json)
  mirrors the expected reviewer lanes for context
- [review_decision_scaffold_input_v1.tsv](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/execution_experience_governance_queue_fixture_bundle_20260311/review_decision_scaffold_input_v1.tsv)
  is the combined scaffold input with one row each for `review_pending`,
  `under_reviewed`, and `decision_ready`
- [governance_queue_summary_v1.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/execution_experience_governance_queue_fixture_bundle_20260311/governance_queue_summary_v1.json)
  records the normalized queue split summary
- [review_pending_v1.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/execution_experience_governance_queue_fixture_bundle_20260311/review_pending_v1.json)
  and [review_pending_v1.tsv](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/execution_experience_governance_queue_fixture_bundle_20260311/review_pending_v1.tsv)
  capture the pending state queue
- [under_reviewed_v1.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/execution_experience_governance_queue_fixture_bundle_20260311/under_reviewed_v1.json)
  and [under_reviewed_v1.tsv](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/execution_experience_governance_queue_fixture_bundle_20260311/under_reviewed_v1.tsv)
  capture the under-reviewed state queue
- [decision_ready_v1.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/execution_experience_governance_queue_fixture_bundle_20260311/decision_ready_v1.json)
  and [decision_ready_v1.tsv](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/execution_experience_governance_queue_fixture_bundle_20260311/decision_ready_v1.tsv)
  capture the ready state queue
- [accept_candidate_v1.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/execution_experience_governance_queue_fixture_bundle_20260311/by_action/accept_candidate_v1.json)
  and [accept_candidate_v1.tsv](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/execution_experience_governance_queue_fixture_bundle_20260311/by_action/accept_candidate_v1.tsv)
  capture the action queue for the ready row

## State and action mapping this bundle demonstrates

For the tracked three-row scaffold input, the exporter yields:

- one state queue file per governance state
- one action queue file per suggested governance action
- a summary that keeps both `by_state` and `by_action` counts

In this minimal fixture:

- `review_pending -> collect_reviews`
- `under_reviewed -> collect_missing_reviews`
- `decision_ready -> accept_candidate`

## Normalization used by the regression

The exporter summary includes absolute temp paths for:

- `input_tsv`
- `output_dir`
- `summary_path`
- nested `queue_files.*.json_path|tsv_path`
- nested `action_files.*.json_path|tsv_path`

The regression normalizes those fields to basenames or queue-relative paths
before comparing against `governance_queue_summary_v1.json`. The emitted queue
file contents themselves are compared directly.

## Why this is still non-conflicting

This bundle does not edit:

- `ops/export_execution_experience_governance_queues.py`
- `ops/build_execution_experience_review_decision_scaffold.py`
- `ops/run_execution_experience_review_cycle.py`
- runtime retrieval / promotion paths
- reviewer orchestration / platform behavior

It only adds tracked fixtures, one regression file, and explanatory docs around
the already-approved governance queue export surface.
