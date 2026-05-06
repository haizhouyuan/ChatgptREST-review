# 2026-03-18 cc-sessiond pending auto-start fix v1

## Problem

`cc-sessiond` sessions could remain in `pending` indefinitely when a caller
created a session without first ensuring the background processor loop had been
started by the FastAPI lifespan.

This was easy to hit from nonstandard entrypoints:

- direct `CCSessionClient.create_session(...)` usage
- route usage outside a full app lifespan startup sequence
- any environment where the singleton client existed but its processor loop was
  not running

## Root Cause

`CCSessionClient.create_session()` only enqueued work. It did not ensure the
processor loop was alive.

The processor loop only started when external code explicitly ran
`CCSessionClient.start()` via the API lifespan. That made session execution
dependent on startup order and calling context.

## Fix

### 1. Make processor startup self-healing

`CCSessionClient.create_session()` now calls `await self.start()` before
submitting the job.

`start()` was changed from a blocking loop into an idempotent "ensure running"
method that spins up a single background processor task.

### 2. Add a dedicated processor loop

The actual loop moved into `_run_processor_loop()`.

This loop:

- keeps polling `scheduler.run_next(...)`
- logs and survives per-iteration exceptions
- clears processor state when the loop exits

### 3. Make shutdown deterministic

`stop()` now waits for the processor task to finish and clears the stored task
reference before cancelling any active job tasks.

### 4. Expose processor health in scheduler status

`get_scheduler_status()` now returns `processor_running`, which makes the
runtime state directly visible from the API.

### 5. Recover stranded sessions on startup

When the processor starts and the in-memory queue is empty, it now scans the
SQLite registry for `pending` / `running` sessions left behind by a previous
stop or restart and requeues them.

If a recovered task packet path is no longer valid, the session is failed
explicitly instead of staying stuck forever.

### 6. Align FastAPI lifespan with new semantics

`_cc_sessiond_lifespan()` no longer wraps `client.start()` in another
`asyncio.create_task(...)`. It now simply awaits the idempotent `start()`.

## Tests

Added / updated tests:

- `tests/test_cc_sessiond.py`
  - `test_create_session_auto_starts_processor_and_completes`
  - `test_start_recovers_pending_session_from_registry`
- `tests/test_cc_sessiond_routes.py`
  - `test_create_session_route_auto_executes`

Validated with:

```bash
./.venv/bin/pytest -q tests/test_cc_sessiond.py
./.venv/bin/pytest -q tests/test_cc_sessiond_routes.py
./.venv/bin/pytest -q tests/test_api_startup_smoke.py
```

## Outcome

`cc-sessiond` no longer relies on external startup ordering to leave `pending`.
Creating a session is now sufficient to start processing.
