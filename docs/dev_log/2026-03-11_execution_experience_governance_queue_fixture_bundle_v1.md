# 2026-03-11 Execution Experience Governance-Queue Fixture Bundle v1

## Goal

Add a tracked fixture bundle for the new execution experience governance queue
surface that mainline just introduced on top of the decision scaffold.

This round stays in `fixture / test / docs` only.

## Artifact root

- `docs/dev_log/artifacts/execution_experience_governance_queue_fixture_bundle_20260311/`

## Included files

1. `experience_candidates_v1.json`
2. `reviewer_manifest_v1.json`
3. `review_decision_scaffold_input_v1.tsv`
4. `governance_queue_summary_v1.json`
5. `review_pending_v1.json`
6. `review_pending_v1.tsv`
7. `under_reviewed_v1.json`
8. `under_reviewed_v1.tsv`
9. `decision_ready_v1.json`
10. `decision_ready_v1.tsv`
11. `by_action/accept_candidate_v1.json`
12. `by_action/accept_candidate_v1.tsv`
13. `README.md`

## What this bundle encodes

The bundle fixes one combined scaffold input containing three governance states:

1. `review_pending`
2. `under_reviewed`
3. `decision_ready`

From that input, the exporter deterministically emits:

- queue files split by governance state
- action queue files under `by_action/`
- a `summary.json` that records counters and emitted file paths

The tracked expected summary is normalized to basenames/relative paths so it
remains stable across temp directories.

## Why this matters

Mainline already landed the governance queue exporter and action queue support.
What was still missing was a tracked fixture surface that makes those split
outputs regression-testable without depending on a live cycle run.

This bundle fills that gap without editing exporter / scaffold / cycle code.

## Validation

The bundle is consumed by:

- [test_execution_experience_governance_queue_fixture_bundle.py](/vol1/1000/projects/ChatgptREST/tests/test_execution_experience_governance_queue_fixture_bundle.py)

The regression:

1. writes the tracked scaffold input TSV into a temp directory
2. runs `export_queues(...)`
3. compares the normalized summary object to `governance_queue_summary_v1.json`
4. compares the emitted state queue files and `by_action/accept_candidate` files
   to the tracked fixtures

## Boundary

This round does **not**:

- modify `ops/export_execution_experience_governance_queues.py`
- modify `ops/build_execution_experience_review_decision_scaffold.py`
- modify `ops/run_execution_experience_review_cycle.py`
- touch runtime adoption
- touch the live `TraceEvent` canonical contract
- do active knowledge promotion
- expand into reviewer orchestration / platform behavior
