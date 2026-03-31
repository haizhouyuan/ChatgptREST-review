# 2026-03-11 Execution Experience Revision-Worklist Fixture Bundle v1

## Goal

Add a tracked fixture bundle for the `revision_worklist.tsv` surface that
mainline just introduced for the revise branch of execution experience review.

This round stays in `fixture / test / docs` only.

## Artifact root

- `docs/dev_log/artifacts/execution_experience_revision_worklist_fixture_bundle_20260311/`

## Included files

1. `experience_candidates_v1.json`
2. `execution_experience_review_decisions_v1.tsv`
3. `revision_worklist_v1.tsv`
4. `revision_worklist_v1_summary.json`
5. `README.md`

## What this bundle encodes

The bundle fixes a two-row reviewed decision input:

1. one `accept`
2. one `revise`

From that input, the worklist builder deterministically filters down to the
single `revise` row and writes:

- `revision_worklist_v1.tsv`
- `revision_worklist_v1.summary.json`

This anchors the revise-only follow-up surface without depending on a live
cycle run.

## Why this matters

Mainline already landed the revision worklist builder and cycle integration.
What was still missing was a tracked fixture surface that makes the revise-only
output regression-testable in isolation.

This bundle fills that gap and keeps the work strictly inside
`fixture / test / docs`.

## Validation

The bundle is consumed by:

- [test_execution_experience_revision_worklist_fixture_bundle.py](/vol1/1000/projects/ChatgptREST/tests/test_execution_experience_revision_worklist_fixture_bundle.py)

The regression:

1. writes tracked candidates and tracked reviewed decision TSV into a temp directory
2. runs `build_worklist(...)`
3. compares the emitted worklist TSV to the tracked fixture
4. compares the normalized summary payload to `revision_worklist_v1_summary.json`

## Boundary

This round does **not**:

- modify `ops/build_execution_experience_revision_worklist.py`
- modify `ops/run_execution_experience_review_cycle.py`
- modify `ops/merge_execution_experience_review_outputs.py`
- touch runtime adoption
- touch the live `TraceEvent` canonical contract
- do active knowledge promotion
- expand into reviewer orchestration / platform behavior
