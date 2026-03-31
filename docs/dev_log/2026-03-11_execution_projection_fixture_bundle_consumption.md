# 2026-03-11 Execution Projection Fixture Bundle Consumption

## Goal

Turn the `#115` projection/mapping supply artifacts into a mainline regression,
without pulling any of that lane into runtime adoption.

## What was added

- `tests/test_execution_projection_fixture_bundle.py`

The test consumes:

- `docs/dev_log/artifacts/execution_projection_fixture_bundle_20260311/runner_adapter_result_codex_batch_v1.json`
- `docs/dev_log/artifacts/execution_projection_fixture_bundle_20260311/telemetry_ingest_execution_run_completed_v1.json`
- `docs/dev_log/artifacts/execution_projection_fixture_bundle_20260311/runner_adapter_projection_split_v1.json`
- `docs/dev_log/artifacts/execution_projection_fixture_bundle_20260311/live_bus_team_run_completed_v1.json`
- `docs/dev_log/artifacts/execution_projection_fixture_bundle_20260311/archive_envelope_agent_task_closeout_v1.json`
- `docs/dev_log/artifacts/execution_projection_fixture_bundle_20260311/live_archive_mapping_split_v1.json`

## Why this matters

Mainline now consumes the supply lane's mapping artifacts as regression
contracts for:

- `runner_adapter.v1 -> telemetry ingest` projection
- `live bus -> archive envelope` lineage mapping

This still does **not**:

- change runtime code
- expand the live event catalog
- introduce an adapter registry

## Validation

- `./.venv/bin/pytest -q tests/test_execution_projection_fixture_bundle.py`
