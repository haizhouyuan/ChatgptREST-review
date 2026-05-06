# 2026-03-11 cc_executor EventBus Smoke

## Goal

Prove that the existing `cc_executor task.*` emitter path reaches canonical
EvoMap through the same `EventBus -> ActivityIngestService` bridge already
validated for wrapper/openclaw/archive envelopes.

## What was added

- `ops/run_cc_executor_eventbus_smoke.py`
- `tests/test_cc_executor_eventbus_smoke.py`

The smoke creates:

- one `task.completed`
- one `task.failed`

using the real `CcExecutor._emit_completion()` and `CcExecutor._emit()` helpers
with an in-memory EventBus + KnowledgeDB + ActivityIngestService.

## Expected result

Canonical atoms are created for:

- `activity: task.completed`
- `activity: task.failed`

and both retain `agent=cc_executor` in applicability.

## Validation

- `./.venv/bin/pytest -q tests/test_cc_executor_eventbus_smoke.py`
- `./.venv/bin/python -m py_compile ops/run_cc_executor_eventbus_smoke.py tests/test_cc_executor_eventbus_smoke.py`
