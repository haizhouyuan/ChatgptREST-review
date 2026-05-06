# 2026-03-11 Execution Experience Review Decision-Scaffold Fixture Bundle Walkthrough v1

## Purpose

This walkthrough explains how the tracked decision-scaffold fixture bundle maps
onto mainline's new controller-facing governance surface.

## Files and roles

- [experience_candidates_v1.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/execution_experience_review_decision_scaffold_fixture_bundle_20260311/experience_candidates_v1.json)
  defines the stable candidate set
- [reviewer_manifest_v1.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/execution_experience_review_decision_scaffold_fixture_bundle_20260311/reviewer_manifest_v1.json)
  defines the expected reviewer lanes
- [execution_experience_review_decisions_partial_v1.tsv](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/execution_experience_review_decision_scaffold_fixture_bundle_20260311/execution_experience_review_decisions_partial_v1.tsv)
  models a candidate that already has a decision row but is still missing two
  expected reviewers
- [execution_experience_review_decisions_complete_v1.tsv](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/execution_experience_review_decision_scaffold_fixture_bundle_20260311/execution_experience_review_decisions_complete_v1.tsv)
  models a candidate whose decision row is fully covered by all expected reviewers
- [review_decision_scaffold_review_pending_v1.tsv](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/execution_experience_review_decision_scaffold_fixture_bundle_20260311/review_decision_scaffold_review_pending_v1.tsv)
  captures the pending state with no decision row at all
- [review_decision_scaffold_under_reviewed_v1.tsv](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/execution_experience_review_decision_scaffold_fixture_bundle_20260311/review_decision_scaffold_under_reviewed_v1.tsv)
  captures the partial-coverage state
- [review_decision_scaffold_decision_ready_v1.tsv](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/execution_experience_review_decision_scaffold_fixture_bundle_20260311/review_decision_scaffold_decision_ready_v1.tsv)
  captures the fully-covered decision-ready state
- the three matching `*_summary_v1.json` files
  record the normalized `by_governance_state` / `by_governance_action` counts

## State mapping this bundle demonstrates

For the same candidate, the builder yields:

1. `review_pending` + `collect_reviews`
   when no decision row exists
2. `under_reviewed` + `collect_missing_reviews`
   when a decision row exists but not all expected reviewers are present
3. `decision_ready` + `accept_candidate`
   when a decision row exists, reviewers are complete, and the review decision
   is already actionable

That directly mirrors the controller-facing governance vocabulary mainline
added in `b32225e`.

## Normalization used by the regression

The builder returns absolute tmp paths in the summary payload. The regression
normalizes:

- `candidates_path`
- `decisions_path`
- `reviewer_manifest_path`
- `output_tsv`
- `summary_path`

down to basenames before comparing to the tracked expected JSON. The TSV output
is compared byte-for-byte.

## Why this is still non-conflicting

This bundle does not edit:

- `ops/build_execution_experience_review_decision_scaffold.py`
- `ops/run_execution_experience_review_cycle.py`
- runtime retrieval / promotion paths
- reviewer orchestration / platform behavior

It only adds tracked fixtures, one regression file, and explanatory docs around
the already-approved scaffold surface.
