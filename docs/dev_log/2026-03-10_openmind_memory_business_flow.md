## Goal

Add one end-to-end business-flow test for the current strategic priority:
OpenMind memory capture and cross-session recall.

## Flow

1. boot app through `create_app()`
2. confirm `/v2/cognitive/health` reports `not_initialized` before any real work
3. capture a user preference through `/v2/memory/capture`
4. confirm health flips to warm/runtime-ready after the first real request
5. resolve context from a different session and verify the captured preference is
   surfaced as remembered guidance
6. verify audit trail and `memory.capture` event evidence inside the runtime

## Why

- this is closer to the real product thesis than isolated unit checks
- it proves the current memory slice is not just API-shaped, but usable as a
  continuity substrate across sessions
- it gives a stable acceptance example for future runtime/bootstrap refactors

## Validation

- `./.venv/bin/pytest -q tests/test_openmind_memory_business_flow.py`
- `./.venv/bin/python -m py_compile tests/test_openmind_memory_business_flow.py`

## Stability note

- the test explicitly clears `OPENMIND_RATE_LIMIT` so its cross-session flow is not
  polluted by security suites that intentionally tighten router rate limits
