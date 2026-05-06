# Conversation Export 429 Cooldown Walkthrough v1

Date: 2026-04-25

## Problem

Two Pro review jobs showed repeated ChatGPT conversation export pressure:

- `87be585c4ef843678d3972b0d27a3452` correctly ended as `needs_followup` with `ProInstantAnswerNeedsRegenerate` after a short confirmation-style Pro answer.
- `e59b2768e866465b828583d715d2f533` continued waiting for usable force-output text, but its wait/export loop repeatedly hit ChatGPT backend API `HTTP 429`.
- `b268223970914aca8bb161b46295919e` was canceled to avoid adding more export polling pressure.

## Root Cause

`chatgpt_web_conversation_export` treats ChatGPT backend API failure as recoverable when DOM fallback can extract messages. That is useful, but the worker treated `ok=true` DOM fallback exports as clean success even when the result still carried `backend_status=429`.

That meant `_maybe_export_conversation` cleared `consecutive_failures` and `cooldown_until` after a degraded export. The next wait slice, or another job in the same account/session, could immediately attempt backend export again after only the normal global minimum interval.

The missing piece was a shared backend-429 cooldown that survives successful DOM fallback.

## Fix

Commit: `2e398c87`

Changes:

- Added a small DB-backed `cooldowns` table and helpers in `chatgptrest.core.rate_limit`.
- Added ChatGPT export backend-429 detection in `chatgptrest.worker.worker`.
- When export returns backend `429`, including `ok=true` DOM fallback exports, the worker now:
  - preserves the exported conversation artifact when available
  - records `conversation_export_backend_rate_limited`
  - writes per-job `ConversationExportBackendRateLimited` state
  - sets a shared cooldown key `chatgpt_web_conversation_export:backend_429`
  - skips later job export attempts with `conversation_export_skipped reason=global_429_cooldown`
- Documented the operator signal and knobs in `docs/runbook.md`.

Defaults:

- `CHATGPTREST_CONVERSATION_EXPORT_429_COOLDOWN_SECONDS=600`
- `CHATGPTREST_CONVERSATION_EXPORT_429_COOLDOWN_MAX_SECONDS=3600`

## Verification

Commands run:

```bash
PYTHONPATH=. ./.venv/bin/python -m py_compile chatgptrest/core/db.py chatgptrest/core/rate_limit.py chatgptrest/worker/worker.py tests/test_conversation_export_force.py
PYTHONPATH=. ./.venv/bin/pytest -q tests/test_conversation_export_force.py tests/test_export_cache.py tests/test_rate_limit_time_rollback.py tests/test_rate_limit_fixed_window.py
PYTHONPATH=. ./.venv/bin/pytest -q tests/test_conversation_export_force.py tests/test_export_cache.py tests/test_worker_and_answer.py -k 'completion_guard or export or wait_phase_finalizes_from_current_answer_when_export_missing_reply or wait_phase_finalizes_from_answer_id_when_export_missing_reply or wait_phase_fails_closed_when_export_thread_is_contaminated'
PYTHONPATH=. ./.venv/bin/pytest -q tests/test_e2e.py
python3 scripts/check_doc_obligations.py --diff HEAD
```

Results:

- `tests/test_conversation_export_force.py` now covers backend `429` plus DOM fallback setting a global cooldown across jobs.
- Targeted export/cache/rate-limit tests passed.
- Worker/export/completion-guard targeted tests passed.
- `tests/test_e2e.py` passed.
- Documentation obligation check reported `docs/runbook.md` present for worker changes.
