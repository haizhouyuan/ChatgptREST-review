# 2026-03-24 Gemini Deep Think Send/Wait Handoff Fix v1

## Problem

`gemini_web.ask + preset=deep_think` could hit a long-running Deep Think generation, time out during the send tool, and then be misclassified as a resend-worthy send failure.

Observed consequences:

- worker kept the job on `phase=send`
- `max_attempts` was consumed on the wrong side of the state machine
- `repair.autofix` could be submitted for a state that was not actually actionable
- real Deep Think runs ended as `MaxAttemptsExceeded` instead of handing off to `wait`

This was not a retry-budget bug. It was a send/wait boundary bug.

## Root Cause

Deep Think send success had been treated too strictly:

- send tool waited for a final/stable answer
- timeout after prompt submission still looked like a generic `TimeoutError`
- worker released Gemini jobs to `wait` only when a stable thread URL already existed

For Deep Think this is wrong. A run can be legitimately in-flight before a stable thread URL is recoverable.

## Fix

### 1. Deep Think timeout taxonomy

`chatgpt_web_mcp/providers/gemini/ask.py`

When `gemini_web_ask_pro_deep_think()` times out after the prompt has already been sent:

- if a new response has started:
  - classify as:
    - `GeminiDeepThinkResponsePending` when a thread URL is already present
    - `GeminiDeepThinkThreadPending` when only the base Gemini app URL is present
  - attach:
    - `wait_handoff_ready=true`
    - `wait_handoff_reason=response_started`
- if no new response started:
  - classify as `GeminiDeepThinkSendUnconfirmed`
  - keep the run on the send side

### 2. Quota-limited Deep Think after send

Still inside `gemini_web_ask_pro_deep_think()`:

- re-scan the page body on exception
- if Gemini shows a quota/usage-limit notice with a reset time:
  - map to `GeminiModeQuotaExceeded`
  - return `status=cooldown`
  - preserve:
    - `retry_after_seconds`
    - `not_before`
    - `reset_at`
    - `quota_notice`

This prevents pointless resend loops when Deep Think is temporarily unavailable until a specific reset time.

### 3. Worker handoff widening for Gemini

`chatgptrest/worker/worker.py`

`_should_release_in_progress_web_job_to_wait()` now releases Gemini jobs to `wait` when any of these are true:

- stable Gemini thread URL exists
- `wait_handoff_ready=true`
- `error_type in {GeminiDeepThinkResponsePending, GeminiDeepThinkThreadPending}`
- `response_started=true`

It still does **not** release when no response evidence exists.

## Autofix Boundary

This fix deliberately avoids making `autofix` more aggressive.

The correct behavior for Deep Think pending states is:

- `response started` -> hand off to `wait`
- `quota limited` -> cooldown until reset
- `send unconfirmed` -> stay on `send` with recovery

These are not Codex-maint repair targets. The state machine should absorb them before `autofix` is considered.

## Validation

Executed:

- `python3 -m py_compile chatgpt_web_mcp/providers/gemini/ask.py chatgptrest/worker/worker.py tests/test_gemini_wait_conversation_hint.py tests/test_worker_and_answer.py`
- `./.venv/bin/pytest -q tests/test_gemini_wait_conversation_hint.py tests/test_gemini_followup_wait_guard.py tests/test_gemini_wait_transient_handling.py tests/test_gemini_deep_think_overloaded.py tests/test_gemini_mode_quota_notice.py tests/test_worker_and_answer.py::test_gemini_send_phase_without_thread_evidence_stays_on_send tests/test_worker_and_answer.py::test_gemini_send_phase_with_response_evidence_requeues_wait tests/test_worker_and_answer.py::test_send_phase_requeues_wait -q`

Result: pass.

## Scope Boundary

This change fixes Deep Think handoff semantics. It does **not** claim:

- full live provider proof
- generic Gemini quality scoring
- arbitrary semantic retry policy
- review-controller level orchestration
