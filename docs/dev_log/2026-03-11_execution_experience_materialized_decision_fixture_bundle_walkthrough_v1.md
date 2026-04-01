# 2026-03-11 Execution Experience Materialized-Decision Fixture Bundle Walkthrough v1

## Purpose

This walkthrough explains how the tracked materialized-decision fixture bundle
maps onto mainline's new reviewed-candidate `by_decision` extraction surface.

## Files and roles

- [experience_candidates_v1.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/execution_experience_materialized_decision_fixture_bundle_20260311/experience_candidates_v1.json)
  defines the candidate metadata used to fill review notes and fallback fields
- [execution_experience_review_decisions_v1.tsv](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/execution_experience_materialized_decision_fixture_bundle_20260311/execution_experience_review_decisions_v1.tsv)
  is the reviewed decision input with one `accept` and one `revise`
- [reviewed_experience_candidates_v1.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/execution_experience_materialized_decision_fixture_bundle_20260311/reviewed_experience_candidates_v1.json)
  and [reviewed_experience_candidates_v1.tsv](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/execution_experience_materialized_decision_fixture_bundle_20260311/reviewed_experience_candidates_v1.tsv)
  capture the full reviewed output set
- [accepted_review_candidates_v1.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/execution_experience_materialized_decision_fixture_bundle_20260311/accepted_review_candidates_v1.json)
  and [accepted_review_candidates_v1.tsv](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/execution_experience_materialized_decision_fixture_bundle_20260311/accepted_review_candidates_v1.tsv)
  capture the combined accepted set, which still includes `revise`
- [accept_v1.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/execution_experience_materialized_decision_fixture_bundle_20260311/by_decision/accept_v1.json)
  and [accept_v1.tsv](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/execution_experience_materialized_decision_fixture_bundle_20260311/by_decision/accept_v1.tsv)
  isolate the `accept` rows
- [revise_v1.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/execution_experience_materialized_decision_fixture_bundle_20260311/by_decision/revise_v1.json)
  and [revise_v1.tsv](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/execution_experience_materialized_decision_fixture_bundle_20260311/by_decision/revise_v1.tsv)
  isolate the `revise` rows
- [summary_v1.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/execution_experience_materialized_decision_fixture_bundle_20260311/summary_v1.json)
  records normalized `by_decision` counts and `decision_files`

## Extraction behavior this bundle demonstrates

The materializer now produces two parallel surfaces:

1. combined reviewed/accepted sets
2. split `by_decision/*` sets

This fixture keeps the example minimal while still proving the key behavior:

- `accepted_review_candidates` includes both `accept` and `revise`
- `by_decision/accept.*` isolates only `accept`
- `by_decision/revise.*` isolates only `revise`

## Normalization used by the regression

The materializer returns absolute temp paths in:

- `output_dir`
- `summary_path`
- `files`
- `decision_files.*.json_path|tsv_path`

The regression normalizes those to basenames or output-relative paths before
comparing against `summary_v1.json`. The emitted file contents themselves are
compared directly.

## Why this is still non-conflicting

This bundle does not edit:

- `ops/merge_execution_experience_review_outputs.py`
- `ops/run_execution_experience_review_cycle.py`
- runtime retrieval / promotion paths
- reviewer orchestration / platform behavior

It only adds tracked fixtures, one regression file, and explanatory docs around
the already-approved reviewed-candidate extraction surface.
