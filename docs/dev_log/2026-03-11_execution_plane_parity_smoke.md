# 2026-03-11 Execution Plane Parity Smoke

## Goal

Lock a narrow parity contract between:

- live execution telemetry materialized by `ActivityIngestService`
- archive/review-plane execution events materialized by `ActivityExtractor`

The purpose is not to unify canonical question shapes or plane-local `source`
labels. It is to ensure the shared execution extensions and correlation fields
remain aligned across both planes.

## What was added

- `ops/run_execution_plane_parity_smoke.py`
- `tests/test_execution_plane_parity_smoke.py`

## Checked fields

- `task_ref`
- `trace_id`
- `lane_id`
- `role_id`
- `adapter_id`
- `profile_id`
- `executor_kind`

## Validation

- `./.venv/bin/pytest -q tests/test_execution_plane_parity_smoke.py tests/test_activity_extractor.py tests/test_activity_ingest.py`
- `./.venv/bin/python ops/run_execution_plane_parity_smoke.py`
