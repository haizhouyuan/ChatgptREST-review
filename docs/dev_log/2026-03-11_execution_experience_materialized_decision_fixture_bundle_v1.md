# 2026-03-11 Execution Experience Materialized-Decision Fixture Bundle v1

## Goal

Add a tracked fixture bundle for the reviewed-candidate `by_decision` extraction
surface that mainline just introduced.

This round stays in `fixture / test / docs` only.

## Artifact root

- `docs/dev_log/artifacts/execution_experience_materialized_decision_fixture_bundle_20260311/`

## Included files

1. `experience_candidates_v1.json`
2. `execution_experience_review_decisions_v1.tsv`
3. `reviewed_experience_candidates_v1.json`
4. `reviewed_experience_candidates_v1.tsv`
5. `accepted_review_candidates_v1.json`
6. `accepted_review_candidates_v1.tsv`
7. `by_decision/accept_v1.json`
8. `by_decision/accept_v1.tsv`
9. `by_decision/revise_v1.json`
10. `by_decision/revise_v1.tsv`
11. `summary_v1.json`
12. `README.md`

## What this bundle encodes

The bundle fixes a two-row reviewed decision set:

1. one `accept`
2. one `revise`

From that input, `materialize_reviewed_candidates(...)` deterministically emits:

- the combined reviewed candidate set
- the combined accepted candidate set
- `by_decision/accept.*`
- `by_decision/revise.*`
- a summary carrying `by_decision` counts and `decision_files`

This anchors the new reviewed-candidate extraction surface without depending on
live review runs.

## Why this matters

Mainline already landed the materialized `by_decision` splits. What was still
missing was a tracked fixture surface that makes those split outputs
regression-testable in isolation.

This bundle fills that gap and keeps the work strictly inside
`fixture / test / docs`.

## Validation

The bundle is consumed by:

- [test_execution_experience_materialized_decision_fixture_bundle.py](/vol1/1000/projects/ChatgptREST/tests/test_execution_experience_materialized_decision_fixture_bundle.py)

The regression:

1. writes tracked candidate JSON and tracked reviewed decision TSV into a temp directory
2. runs `materialize_reviewed_candidates(...)`
3. compares the normalized summary payload to `summary_v1.json`
4. compares the combined reviewed/accepted outputs and `by_decision/accept|revise`
   outputs to the tracked fixtures

## Boundary

This round does **not**:

- modify `ops/merge_execution_experience_review_outputs.py`
- modify `ops/run_execution_experience_review_cycle.py`
- touch runtime adoption
- touch the live `TraceEvent` canonical contract
- do active knowledge promotion
- expand into reviewer orchestration / platform behavior
