# 2026-03-11 Execution Experience Controller-Rollup-Manifest Fixture Bundle v1

## Goal

Add a tracked fixture bundle for the machine-readable
`controller_rollup_manifest.json` surface that mainline just introduced.

This round stays in `fixture / test / docs` only.

## Artifact root

- `docs/dev_log/artifacts/execution_experience_controller_rollup_manifest_fixture_bundle_20260311/`

## Included files

1. `first_cycle_controller_rollup_manifest_v1.json`
2. `second_cycle_controller_rollup_manifest_v1.json`
3. `README.md`

## What this bundle encodes

The tracked fixtures cover the two rollup-manifest states that matter for the
current controller contract:

1. first cycle
   - `availability.progress_delta = false`
   - `summary.progress_signal = ""`
2. later cycle
   - `availability.progress_delta = true`
   - `summary.progress_signal = unchanged`

Both snapshots pin the fields mainline explicitly called out:

- `summary`
- `paths`
- `availability`
- `artifacts`
- `constraints`

## Why this matters

Mainline already landed the rollup-manifest builder and cycle wiring. What was
still missing was a tracked JSON surface that freezes:

- the first-cycle shape before `progress_delta.json` exists
- the later-cycle shape after `progress_delta.json` is materialized

This bundle fills that gap without touching the builder or the cycle.

## Validation

The bundle is consumed by:

- [test_execution_experience_controller_rollup_manifest_fixture_bundle.py](/vol1/1000/projects/ChatgptREST/tests/test_execution_experience_controller_rollup_manifest_fixture_bundle.py)

The regression:

1. seeds the minimal review DB and decision TSV
2. runs the cycle once
3. snapshots the first-cycle `controller_rollup_manifest.json`
4. runs the cycle a second time
5. snapshots the later-cycle `controller_rollup_manifest.json`
6. normalizes temp-root and dynamic cycle-dir path drift
7. compares both manifests against tracked JSON fixtures

## Boundary

This round does **not**:

- modify `ops/build_execution_experience_controller_rollup_manifest.py`
- modify `ops/run_execution_experience_review_cycle.py`
- touch runtime adoption
- touch the live `TraceEvent` canonical contract
- do active knowledge promotion
