# 2026-03-11 Execution Experience Followup-Manifest Fixture Bundle v1

## Goal

Add a tracked fixture bundle for the controller-facing `followup_manifest.json`
surface that mainline just introduced.

This round stays in `fixture / test / docs` only.

## Artifact root

- `docs/dev_log/artifacts/execution_experience_followup_manifest_fixture_bundle_20260311/`

## Included files

1. `acceptance_pack_input_v1.json`
2. `revision_worklist_input_v1.json`
3. `deferred_revisit_queue_input_v1.json`
4. `rejected_archive_queue_input_v1.json`
5. `followup_manifest_v1.json`
6. `README.md`

## What this bundle encodes

The tracked inputs model the four branch summaries that the cycle already has in
memory when it calls `build_manifest(...)`:

- `accept` with `accepted_candidates = 2`
- `revise` with `total_revise_candidates = 1`
- `defer` with `total_deferred_candidates = 3`
- `reject` with `total_rejected_candidates = 4`

From those four inputs, the builder deterministically emits one
`followup_manifest.json` whose job is only to summarize branch counts and
handoff paths.

## Why this matters

Mainline already landed the followup-manifest builder and cycle wiring. What was
still missing was a tracked, replayable fixture surface that freezes:

- the four branch names
- their per-branch count fields
- the controller-facing path slots
- the `total_followup_candidates` rollup

This bundle fills that gap without touching runtime behavior.

## Validation

The bundle is consumed by:

- [test_execution_experience_followup_manifest_fixture_bundle.py](/vol1/1000/projects/ChatgptREST/tests/test_execution_experience_followup_manifest_fixture_bundle.py)

The regression:

1. loads tracked branch-summary inputs
2. rewrites their paths into a temp directory
3. runs `build_manifest(...)`
4. compares the emitted JSON against tracked `followup_manifest_v1.json`

## Boundary

This round does **not**:

- modify `ops/build_execution_experience_followup_manifest.py`
- modify `ops/run_execution_experience_review_cycle.py`
- touch runtime adoption
- touch the live `TraceEvent` canonical contract
- do active knowledge promotion
- expand into reviewer orchestration / platform behavior
