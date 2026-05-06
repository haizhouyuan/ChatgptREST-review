# 2026-03-11 Execution Experience Progress-Delta Fixture Bundle v1

## Goal

Add a tracked fixture bundle for the controller-facing `progress_delta.json`
surface that mainline just introduced.

This round stays in `fixture / test / docs` only.

## Artifact root

- `docs/dev_log/artifacts/execution_experience_progress_delta_fixture_bundle_20260311/`

## Included files

1. `improved_previous_governance_snapshot_input_v1.json`
2. `improved_current_governance_snapshot_input_v1.json`
3. `improved_previous_controller_action_plan_input_v1.json`
4. `improved_current_controller_action_plan_input_v1.json`
5. `improved_progress_delta_v1.json`
6. `regressed_previous_governance_snapshot_input_v1.json`
7. `regressed_current_governance_snapshot_input_v1.json`
8. `regressed_previous_controller_action_plan_input_v1.json`
9. `regressed_current_controller_action_plan_input_v1.json`
10. `regressed_progress_delta_v1.json`
11. `README.md`

## What this bundle encodes

The tracked fixtures cover the two delta shapes that mainline explicitly asked
to freeze:

1. `improved`
2. `regressed`

Each case fixes four builder inputs:

- previous `governance_snapshot.json`
- current `governance_snapshot.json`
- previous `controller_action_plan.json`
- current `controller_action_plan.json`

And one expected output:

- `progress_delta.json`

## Why this matters

Mainline already landed the progress-delta builder. What was still missing was a
replayable fixture surface that freezes:

- previous/current totals
- validation delta
- queue delta
- attention-flag flips
- `progress_signal`

for the two controller-visible extremes: improvement and regression.

## Validation

The bundle is consumed by:

- [test_execution_experience_progress_delta_fixture_bundle.py](/vol1/1000/projects/ChatgptREST/tests/test_execution_experience_progress_delta_fixture_bundle.py)

The regression:

1. loads tracked previous/current governance snapshots and action plans
2. rewrites their `output_path` fields into a temp directory
3. runs `build_delta(...)`
4. compares the emitted JSON against tracked expected output

## Boundary

This round does **not**:

- modify `ops/build_execution_experience_progress_delta.py`
- touch runtime adoption
- touch the live `TraceEvent` canonical contract
- do active knowledge promotion
- expand into reviewer orchestration / platform behavior
