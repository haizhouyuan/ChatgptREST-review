# 2026-04-07 OpenMind Plugins Project Scope Propagation Walkthrough v1

## What changed

This batch completes the `E` line needed after the core `project_id` substrate work:

1. `openmind-advisor` now resolves `projectRef -> project_id` and injects the value into `task_intake.available_inputs.project_id`.
2. `openmind-memory` now infers, caches, and propagates `project_id` across manual recall, manual capture, `before_agent_start`, and `agent_end`.
3. `openmind-telemetry` now infers, caches, and propagates `project_id` into telemetry queue items and lifecycle events.
4. `/v2/memory/capture` and `/v2/telemetry/ingest` now accept top-level `project_id`.
5. `MemoryCaptureService` and `TelemetryIngestService` now preserve `project_id` when mirroring plugin traffic into memory and feedback records.
6. Added a PRS authority-anchor file at `/vol1/1000/projects/planning/行星滚柱丝杠/_project_context.md` so the advisor registry no longer points at a missing file.

## Why

The previous state had a gap:

- `project_id` had already been threaded into the backend substrate hot path.
- `projectRef` existed in the advisor plugin.
- but the plugin layer still dropped project scope before memory capture, telemetry ingest, and context recall.

That meant:

- OpenClaw project routing could attach project context once,
- but downstream memory, telemetry, and recall would behave as if the session had no stable project scope.

This batch closes that gap.

## Code paths changed

### OpenClaw extensions

- `openclaw_extensions/openmind-advisor/index.ts`
- `openclaw_extensions/openmind-memory/index.ts`
- `openclaw_extensions/openmind-telemetry/index.ts`

### Backend contracts and services

- `chatgptrest/api/routes_cognitive.py`
- `chatgptrest/cognitive/memory_capture_service.py`
- `chatgptrest/cognitive/telemetry_service.py`
- `chatgptrest/telemetry_contract.py`

### Tests

- `tests/test_openclaw_cognitive_plugins.py`
- `tests/test_capture_work_memory.py`
- `tests/test_cognitive_api.py`
- `tests/test_advisor_runtime.py`

## Key implementation notes

### Advisor plugin

- Added canonical `projectId` handling to loaded project contexts.
- Mapped known refs and aliases to normalized project ids.
- Propagated `project_id` into `available_inputs` so backend runtime can continue using the same scope.

### Memory plugin

- Added project inference from prompt text using conservative, high-signal patterns.
- Added per-session project cache so later hooks can reuse the same scope.
- Included `project_id` in both resolve and capture calls.
- Included project scope in the recall cache key to avoid cross-project reuse.

### Telemetry plugin

- Added the same infer/cache/propagate pattern used by the memory plugin.
- Lifecycle queue items now carry `project_id` at the top level and inside `data.project_id`.

### Backend

- The cognitive REST models now accept `project_id` for capture and telemetry ingest.
- Memory capture now preserves `project_id` both in stored value payloads and in `MemorySource`.
- Telemetry ingest now preserves `project_id` through identity extraction and feedback mirroring.

## Validation

Executed:

```bash
./.venv/bin/pytest -q \
  tests/test_openclaw_cognitive_plugins.py \
  tests/test_capture_work_memory.py \
  tests/test_cognitive_api.py \
  tests/test_advisor_runtime.py
```

Result:

- `61 passed`

## Risk

- Plugin-side symbol blast radius was low.
- Backend changes touched contract surfaces for memory capture and telemetry ingest, so the main risk is schema drift.
- Regression coverage explicitly checks:
  - plugin propagation,
  - project-scoped memory capture,
  - project-scoped context resolve,
  - telemetry-to-memory mirroring.

## Follow-up

This completes the plugin/runtime propagation needed before broader OpenClaw project-aware routing hardening.
The next main line remains `F`: diagnose and recover the promotion pipeline, then add harness coverage around project-scoped retrieval and authority adherence.
