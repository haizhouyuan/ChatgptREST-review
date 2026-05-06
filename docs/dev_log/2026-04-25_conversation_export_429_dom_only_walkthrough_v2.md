# Conversation Export 429 DOM-Only Follow-Up Walkthrough v2

Date: 2026-04-25

## Trigger

After the first shared cooldown fix, a force-output Pro follow-up job
`da8fb6f87f0f4e84a2f1b39ebab194f5` hit another ChatGPT conversation backend
`HTTP 429` at 17:56:55. This was after the manually seeded shared cooldown
expired at 17:56:32.

## Findings

- The new worker code did detect the degraded export and wrote
  `conversation_export_backend_rate_limited`.
- The send worker was still an old process from 07:54, so runtime had only
  partially picked up the previous fix. It was restarted at 17:57.
- A fixed backend cooldown still leaves one backend probe at cooldown expiry.
  If ChatGPT remains rate-limited, that probe can produce another 429 even
  though DOM fallback is enough for completion-guard reconciliation.

## Fix

- `chatgpt_web_conversation_export` now accepts `backend_mode=dom_only`.
- During shared backend-429 cooldown, `_maybe_export_conversation(..., force=True)`
  calls the driver with `backend_mode=dom_only` instead of skipping the evidence
  export or probing the backend API.
- Non-force exports still skip while the shared cooldown is active.
- The worker records `conversation_export_backend_skipped` when it deliberately
  suppresses the backend fetch and proceeds with DOM-only export.

## Validation

- `py_compile` for the driver, worker, and regression test.
- `tests/test_conversation_export_force.py` validates:
  - backend 429 with DOM fallback seeds shared cooldown,
  - force export during shared cooldown uses `backend_mode=dom_only`,
  - non-force export during shared cooldown still skips.
- `tests/test_export_cache.py`, `tests/test_rate_limit_time_rollback.py`, and
  `tests/test_rate_limit_fixed_window.py` stayed green.

## Operational Note

The currently affected Pro jobs are not usable external-review evidence:

- `220bfc0777eb4ca2accd064d39c2633e`: `needs_followup`,
  `ProInstantAnswerNeedsRegenerate`.
- `e59b2768e866465b828583d715d2f533`: `needs_followup`,
  `WebRetryBudgetExceeded`.
- `da8fb6f87f0f4e84a2f1b39ebab194f5`: `needs_followup`,
  `ProInstantAnswerNeedsRegenerate`.

Do not create more same-conversation Pro retries until the cooldown has drained
and the operator intentionally decides whether another follow-up is warranted.
