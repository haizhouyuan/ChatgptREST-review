# 2026-03-11 Execution Experience Acceptance-Pack Fixture Bundle v1

## Goal

Add a tracked fixture bundle for the `accepted_pack/` surface that mainline
just introduced for the accept branch of execution experience review.

This round stays in `fixture / test / docs` only.

## Artifact root

- `docs/dev_log/artifacts/execution_experience_acceptance_pack_fixture_bundle_20260311/`

## Included files

1. `experience_candidates_v1.json`
2. `execution_experience_review_decisions_v1.tsv`
3. `accepted_candidates_v1.json`
4. `accepted_candidates_v1.tsv`
5. `manifest_v1.json`
6. `smoke_manifest_v1.json`
7. `README.md`

## What this bundle encodes

The bundle fixes a two-row reviewed decision input:

1. one `accept`
2. one `revise`

From that input, the acceptance-pack exporter deterministically filters down to
the single `accept` row and writes:

- `accepted_candidates.json`
- `accepted_candidates.tsv`
- `manifest.json`
- `smoke_manifest.json`

The tracked manifest keeps the review-plane-only boundary explicit:

- `review_plane_only = true`
- `default_runtime_cutover = false`
- `active_knowledge_promotion = false`

## Why this matters

Mainline already landed the acceptance-pack exporter and cycle wiring. What was
still missing was a tracked fixture surface that makes the accept-only handoff
artifact regression-testable in isolation.

This bundle fills that gap and keeps the work strictly inside
`fixture / test / docs`.

## Validation

The bundle is consumed by:

- [test_execution_experience_acceptance_pack_fixture_bundle.py](/vol1/1000/projects/ChatgptREST/tests/test_execution_experience_acceptance_pack_fixture_bundle.py)

The regression:

1. writes tracked candidates and reviewed decision TSV into a temp directory
2. runs `export_pack(...)`
3. compares the emitted `accepted_candidates.json|tsv`
4. compares a normalized `manifest.json`
5. compares `smoke_manifest.json`

## Boundary

This round does **not**:

- modify `ops/export_execution_experience_acceptance_pack.py`
- modify `ops/run_execution_experience_review_cycle.py`
- modify `ops/merge_execution_experience_review_outputs.py`
- touch runtime adoption
- touch the live `TraceEvent` canonical contract
- do active knowledge promotion
- expand into reviewer orchestration / platform behavior
