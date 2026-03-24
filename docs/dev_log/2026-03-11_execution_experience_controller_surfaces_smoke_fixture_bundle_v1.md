# 2026-03-11 Execution Experience Controller-Surfaces Smoke Fixture Bundle v1

## Goal

Add a tracked fixture bundle for the seeded
`run_execution_experience_controller_surfaces_smoke.py` surface that mainline
just introduced.

This round stays in `fixture / test / docs` only.

## Artifact root

- `docs/dev_log/artifacts/execution_experience_controller_surfaces_smoke_fixture_bundle_20260311/`

## Included files

1. `controller_surfaces_smoke_summary_v1.json`
2. `controller_packet_v1.json`
3. `controller_action_plan_v1.json`
4. `review_brief_v1.md`
5. `review_reply_draft_v1.md`
6. `README.md`

## What this bundle encodes

The tracked fixtures freeze the deterministic seeded smoke outputs for the
controller-facing review chain:

- `controller_surfaces_smoke_summary.json`
- `controller_packet.json`
- `controller_action_plan.json`
- `review_brief.md`
- `review_reply_draft.md`

The sample reflects the current seeded smoke shape:

- `mode = refresh_merge_only`
- `recommended_action = collect_missing_reviews`
- `reason = review coverage is incomplete`

## Why this matters

Mainline already landed the smoke runner and its focused runtime test. What was
still missing was a tracked output bundle that makes the full controller-facing
surface regression-testable as one deterministic snapshot set.

This bundle fills that gap without changing any builder or the smoke runner.

## Validation

The bundle is consumed by:

- [test_execution_experience_controller_surfaces_smoke_fixture_bundle.py](/vol1/1000/projects/ChatgptREST/tests/test_execution_experience_controller_surfaces_smoke_fixture_bundle.py)

The regression:

1. runs the seeded smoke
2. locates the emitted summary and the four referenced controller-facing files
3. normalizes temp-root and cycle-dir paths
4. compares all five outputs against tracked snapshots

## Boundary

This round does **not**:

- modify `ops/run_execution_experience_controller_surfaces_smoke.py`
- modify `ops/run_execution_experience_review_cycle.py`
- modify any controller-surface builder
- touch runtime adoption
- touch the live `TraceEvent` canonical contract
- do active knowledge promotion
