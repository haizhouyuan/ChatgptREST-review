# 2026-03-11 Planning Review Refresh Pipeline v1

## Goal

Turn the `planning -> EvoMap` workstream from a one-shot import into a repeatable refresh path:

- build a new review-plane snapshot
- compare against the previous snapshot
- generate a delta-only review pack for changed or unreviewed service candidates

## Added

- [planning_review_refresh.py](/vol1/1000/projects/ChatgptREST/chatgptrest/evomap/knowledge/planning_review_refresh.py)
- [run_planning_review_refresh.py](/vol1/1000/projects/ChatgptREST/ops/run_planning_review_refresh.py)
- [test_planning_review_refresh.py](/vol1/1000/projects/ChatgptREST/tests/test_planning_review_refresh.py)

## What It Produces

For each refresh run:

- `role_changed.tsv`
- `added_service_candidates.tsv`
- `removed_service_candidates.tsv`
- `review_needed.tsv`
- optional `planning_incremental_review_pack_v1.json`
- `summary.json`

The intent is to keep future review work on the changed slice instead of re-reviewing the full `planning` candidate pool every time.

## Decision Baseline

Refresh does not treat the previous refresh snapshot as the only truth source.

- role and candidate diffs compare against the previous refresh snapshot
- review completeness compares against the latest review-plane snapshot that already carries `planning_review_decisions*.tsv`

That keeps the delta pack anchored to the last reviewed planning baseline instead of re-flagging the entire allowlist on every refresh run.

## Boundary

This is still a `review-plane` tool, not a runtime retrieval cutover.
