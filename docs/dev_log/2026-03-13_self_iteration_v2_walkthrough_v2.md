# 2026-03-13 Self-Iteration V2 Walkthrough v2

## Scope
- Completed Slice B: execution identity contract.
- This build follows the Slice A policy freeze and remains pre-parallel-lanes.

## What changed
- Extended `chatgptrest/telemetry_contract.py` so normalized identity now includes:
  - `logical_task_id`
  - `identity_confidence`
- Added execution identity derivation rules:
  - explicit `logical_task_id` => `authoritative`
  - unambiguous `task_id` => `derived_task_id`
  - only `task_ref` present => `task_ref_only`
  - only trace/run/job available => `execution_only`
  - otherwise => `partial`
- Extended retrieval telemetry storage (`query_events`) to persist:
  - `trace_id`
  - `run_id`
  - `job_id`
  - `task_ref`
  - `logical_task_id`
  - `identity_confidence`
- Updated recall telemetry wiring so `/v1/advisor/recall` can carry and return normalized execution identity instead of only a `query_id`.
- Updated cognitive telemetry ingest so live execution events can carry `logical_task_id` through event bus payloads.
- Updated telemetry feedback memory mirroring so episodic execution feedback prefers `logical_task_id` over `task_ref`, then falls back to `trace_id` only if needed.
- Added `advisor_runs.execution_identity_for_run()` to expose a single normalized execution-identity helper from the durable run spine.

## Why
- Slice A made runtime retrieval policy explicit.
- Slice B makes execution lineage explicit enough for later outcome-ledger and evaluator slices.
- Without this step, later lanes would each invent their own task/run/job mapping.

## Verification
- `python3 -m py_compile chatgptrest/telemetry_contract.py chatgptrest/evomap/knowledge/telemetry.py chatgptrest/api/routes_consult.py chatgptrest/cognitive/telemetry_service.py chatgptrest/api/routes_cognitive.py chatgptrest/core/advisor_runs.py tests/test_telemetry_contract.py tests/test_cognitive_api.py tests/test_advisor_consult.py tests/test_execution_identity_contract.py`
- `/vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q tests/test_telemetry_contract.py tests/test_cognitive_api.py tests/test_advisor_consult.py tests/test_execution_identity_contract.py tests/test_advisor_runtime.py`

## Key assertions now locked by tests
- Explicit `logical_task_id` is preserved with `identity_confidence=authoritative`.
- Unambiguous `task_id` is promoted to `logical_task_id` with `identity_confidence=derived_task_id`.
- `/v2/telemetry/ingest` preserves `logical_task_id` and `identity_confidence` in live event payloads.
- `/v1/advisor/recall` records execution identity into `query_events` and returns `query_identity` alongside `query_id`.
- `advisor_runs.execution_identity_for_run()` derives a stable chain from the durable run record.

## Remaining work
- Shared contract is now frozen enough to start bounded parallel lanes.
- Next step: launch C/D/E/F lanes with disjoint write scopes.
