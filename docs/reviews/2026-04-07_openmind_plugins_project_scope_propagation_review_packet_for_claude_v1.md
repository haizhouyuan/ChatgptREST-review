# 2026-04-07 OpenMind Plugins Project Scope Propagation Review Packet for Claude v1

## Review target

This packet covers the `E` line of the execution plan:

- OpenClaw/OpenMind plugin propagation of `project_id`
- backend acceptance of plugin-supplied `project_id`
- memory / telemetry preservation of project scope
- PRS authority-anchor file availability for advisor registry

## Expected behavior after this batch

1. `openmind-advisor` carries a normalized `project_id` whenever a known `projectRef` is supplied.
2. `openmind-memory` can recall and capture with stable project scope across a session.
3. `openmind-telemetry` can emit project-aware lifecycle events and feedback payloads.
4. `/v2/memory/capture` and `/v2/telemetry/ingest` no longer drop `project_id`.
5. Mirrored work memory and execution feedback stay queryable by `project_id`.
6. Both registered advisor project context files exist:
   - shortmobility
   - prs

## Files changed

### Product/runtime code

- `openclaw_extensions/openmind-advisor/index.ts`
- `openclaw_extensions/openmind-memory/index.ts`
- `openclaw_extensions/openmind-telemetry/index.ts`
- `chatgptrest/api/routes_cognitive.py`
- `chatgptrest/cognitive/memory_capture_service.py`
- `chatgptrest/cognitive/telemetry_service.py`
- `chatgptrest/telemetry_contract.py`

### Tests

- `tests/test_openclaw_cognitive_plugins.py`
- `tests/test_capture_work_memory.py`
- `tests/test_cognitive_api.py`
- `tests/test_advisor_runtime.py`

### External authority anchor

- `/vol1/1000/projects/planning/行星滚柱丝杠/_project_context.md`

## Review questions

1. Does `project_id` now travel cleanly from plugin hooks into backend capture and telemetry services without being dropped?
2. Is the project inference/cache strategy conservative enough to avoid accidental cross-project contamination?
3. Are `MemoryCaptureService` and `TelemetryIngestService` preserving project scope in both the stored payload and `MemorySource` metadata?
4. Do the tests cover both:
   - scoped visibility,
   - scoped isolation?
5. Is there any remaining path where plugin-provided `project_id` can be lost before project-scoped retrieval reads it back?

## Required red-team focus

- Session starts on project A, later receives generic follow-up text: does the cache retain the correct project rather than dropping scope?
- Manual capture or telemetry ingest without project scope: does behavior stay backward-compatible?
- Context resolve with `project_id=shortmobility` should not surface `prs` memory and vice versa.
- Advisor registry should not point to a missing project context file.

## Local validation already run

```bash
./.venv/bin/pytest -q \
  tests/test_openclaw_cognitive_plugins.py \
  tests/test_capture_work_memory.py \
  tests/test_cognitive_api.py \
  tests/test_advisor_runtime.py
```

Observed result:

- `61 passed`

## Intended blast radius

- OpenClaw plugin layer
- cognitive API request models for capture and telemetry ingest
- memory/telemetry persistence metadata

No intentional behavior changes to:

- public agent MCP
- jobs API
- planning task plane
- low-level web executors
