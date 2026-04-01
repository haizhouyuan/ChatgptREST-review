# 2026-03-11 Execution Experience Review Decision-Scaffold Fixture Bundle v1

## Goal

Add a tracked fixture bundle for the controller-facing execution experience
decision scaffold surface that mainline just introduced.

This round stays in `fixture / test / docs` only.

## Artifact root

- `docs/dev_log/artifacts/execution_experience_review_decision_scaffold_fixture_bundle_20260311/`

## Included files

1. `experience_candidates_v1.json`
2. `reviewer_manifest_v1.json`
3. `execution_experience_review_decisions_partial_v1.tsv`
4. `execution_experience_review_decisions_complete_v1.tsv`
5. `review_decision_scaffold_review_pending_v1.tsv`
6. `review_decision_scaffold_review_pending_v1_summary.json`
7. `review_decision_scaffold_under_reviewed_v1.tsv`
8. `review_decision_scaffold_under_reviewed_v1_summary.json`
9. `review_decision_scaffold_decision_ready_v1.tsv`
10. `review_decision_scaffold_decision_ready_v1_summary.json`
11. `README.md`

## What this bundle encodes

The bundle fixes three deterministic governance states for the same candidate
universe:

1. `review_pending`
   with no decision TSV present
2. `under_reviewed`
   with a partial decision row backed by one reviewer only
3. `decision_ready`
   with a complete decision row backed by all expected reviewers

This anchors both the TSV handoff surface and the `.summary.json` counts that
mainline wants controllers to consume.

## Why this matters

Mainline already landed the decision scaffold builder and cycle integration.
What was still missing was a tracked fixture surface that makes the scaffold
states and counts regression-testable without live DB/archive inputs.

This bundle fills that gap and keeps the work inside `fixture / test / docs`.

## Validation

The bundle is consumed by:

- [test_execution_experience_review_decision_scaffold_fixture_bundle.py](/vol1/1000/projects/ChatgptREST/tests/test_execution_experience_review_decision_scaffold_fixture_bundle.py)

The regression replays the current builder three times:

1. no decisions file -> `review_pending`
2. partial decisions file -> `under_reviewed`
3. complete decisions file -> `decision_ready`

In each case it compares both the emitted TSV and the normalized summary object
against the tracked fixtures.

## Boundary

This round does **not**:

- modify `ops/build_execution_experience_review_decision_scaffold.py`
- modify `ops/run_execution_experience_review_cycle.py`
- touch runtime adoption
- touch the live `TraceEvent` canonical contract
- do active knowledge promotion
- expand into reviewer orchestration / platform behavior
