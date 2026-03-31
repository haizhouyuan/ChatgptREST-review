# 2026-03-27 low-level ask dedupe error retry fix v1

## Problem

Low-level ask runtime dedupe was intended to block only recent duplicate submissions that were still active or otherwise meaningful to suppress.

The SQL filter in `chatgptrest/core/ask_guard.py` used:

- `status NOT IN ('failed', 'canceled')`

But the actual state machine uses:

- `error`
- `canceled`

There is no `failed` status in `chatgptrest/core/state_machine.py`.

As a result, a request that had just transitioned to `error` still matched the dedupe window and was rejected as:

- `409 low_level_ask_duplicate_recently_submitted`

That incorrectly blocked immediate retry after a failed low-level ask.

## Fix

- Changed the dedupe query to exclude `error` and `canceled`.
- Added a regression test that:
  - submits a signed `planning-wrapper` low-level ask
  - mutates the first job to `status=error`
  - resubmits the same request
  - verifies the retry is accepted and creates a new job instead of returning 409

## Validation

- `./.venv/bin/python -m py_compile chatgptrest/core/ask_guard.py tests/test_low_level_ask_guard.py`
- `./.venv/bin/pytest -q tests/test_low_level_ask_guard.py -k 'blocks_recent_duplicate or allows_immediate_retry_after_error'`
