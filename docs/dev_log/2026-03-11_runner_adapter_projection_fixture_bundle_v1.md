# 2026-03-11 Runner Adapter Projection Fixture Bundle v1

## Goal

Provide fixture-driven projection examples for the next `#115` contract-supply
step:

- start from `runner_adapter.v1`
- project into a telemetry-ingest payload
- keep root canonical and execution extensions explicitly separated

This bundle does not change runtime code and does not expand the live event
catalog.

## Artifact files

Artifact root:

- `docs/dev_log/artifacts/execution_projection_fixture_bundle_20260311/`

Included projection artifacts:

1. `runner_adapter_result_codex_batch_v1.json`
2. `telemetry_ingest_execution_run_completed_v1.json`
3. `runner_adapter_projection_split_v1.json`

## Projection boundary

### Root canonical

- `event_type`
- `source`
- `trace_id`
- `session_id`
- `run_id`
- `task_ref`
- `repo_name`
- `repo_path`
- `agent_name`
- `agent_source`

### Execution extensions

- `lane_id`
- `adapter_id`
- `profile_id`
- `executor_kind`

### Event payload metadata

- `adapter_ticket_id`
- `fallback_used`
- `approval_mode_effective`
- `cost`
- `result_type`
- `output_ref`
- `state`

## Why this bundle exists

Mainline explicitly asked the `#115` line to continue supplying projection and
mapping artifacts without entering runtime adoption.

This bundle answers the first half of that ask:

- one minimal adapter result fixture
- one minimal telemetry-ingest projection fixture
- one machine-readable split that says what lands in root canonical, what stays
  as execution extensions, and what remains event payload metadata

## Intended use

- review on `#115`
- future fixture-driven projection tests if mainline wants them later
- reference material for a future `runner_adapter.v1 -> telemetry ingest`
  adapter without implementing it now
