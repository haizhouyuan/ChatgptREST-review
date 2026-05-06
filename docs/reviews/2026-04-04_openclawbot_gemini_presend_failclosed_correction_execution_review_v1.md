# 2026-04-04 OpenClawBot Gemini Pre-Send Fail-Closed Correction Execution Review v1

## Scope

This batch corrects a worker-side misclassification in the OpenClawBot planning live path.

The concrete issue was: Gemini jobs that timed out **before send actually started** could still be converted by the worker into `GeminiBlankSendTimeout`, which made the live gate report a misleading blank-send failure instead of the real pre-send prompt-surface failure.

## Evidence That Motivated The Fix

Two live jobs from the previous gate run showed the same pattern:

- `c69de8d011a640d29a4aa8c071591745`
- `b55f9e44035e4904ae02df53b868f6a7`

Their persisted `result.json` failed as `GeminiBlankSendTimeout`, but their `run_meta.json` proved the provider never reached send:

- `error_type=TimeoutError`
- `debug_step=find_prompt_box_initial`
- `conversation_url=""`

That means these were **pre-send Gemini prompt-surface timeouts**, not true blank-send-without-thread cases.

## Code Change

Changed file:

- `chatgptrest/worker/worker.py`

Key adjustment:

- Introduced `_GEMINI_PRE_SEND_DEBUG_STEPS`
- `_should_fail_closed_blank_gemini_send_cooldown(...)` now accepts `meta`
- Fail-closed is skipped when Gemini explicitly reports a pre-send debug step such as:
  - `open_page`
  - `new_chat`
  - `find_prompt_box_initial`
  - `import_code`
  - `attach_drive_files`
  - `prepare_prompt`
  - `pre_send_quota_check`
  - `find_prompt_box_send`
  - `type_question`

This keeps the existing blank-send protection for ambiguous timeout/cooldown cases, while preventing obvious pre-send UI failures from being mislabeled as blank send.

## Regression Coverage

Changed test file:

- `tests/test_worker_and_answer.py`

Added regression:

- `test_worker_does_not_fail_close_pre_send_gemini_prompt_box_timeout`

Confirmed existing protections still pass:

- `test_worker_fail_closes_blank_gemini_send_timeout_without_thread`
- `test_worker_fail_closes_blank_gemini_executor_cooldown_without_thread`
- `test_gemini_send_phase_with_pending_recovery_requeues_wait`
- `test_gemini_send_phase_with_response_evidence_requeues_wait`

## Validation Run

Executed successfully:

```bash
python3 -m py_compile chatgptrest/worker/worker.py tests/test_worker_and_answer.py
./.venv/bin/pytest -q \
  tests/test_worker_and_answer.py::test_worker_fail_closes_blank_gemini_send_timeout_without_thread \
  tests/test_worker_and_answer.py::test_worker_fail_closes_blank_gemini_executor_cooldown_without_thread \
  tests/test_worker_and_answer.py::test_worker_does_not_fail_close_pre_send_gemini_prompt_box_timeout \
  tests/test_worker_and_answer.py::test_gemini_send_phase_with_pending_recovery_requeues_wait \
  tests/test_worker_and_answer.py::test_gemini_send_phase_with_response_evidence_requeues_wait
```

## Live Re-Run Signal

A new live gate rerun was started with artifact dir:

- `docs/dev_log/artifacts/openclawbot_planning_task_plane_live_completion_gate_20260404_v4/`

The current live session is:

- `openclaw-live-planning-completion-session-5370b116`

At the time of this freeze, the new backing job was:

- `d110c511427044c5ae86a4e806d5840c`

Crucially, this run no longer immediately surfaced as `GeminiBlankSendTimeout`. The observed state moved to:

- job status: `queued`
- phase: `send`
- event: `job_deferred_by_pause`
- reason: `auto_blocked:cloudflare`

This is not success yet, but it is a better failure boundary: the system is now exposing the pause/Cloudflare condition instead of falsely collapsing the run into blank-send fail-closed.

## Current Independent Judgment

This patch is correct and should stay.

It does **not** solve the whole W1 live path. What it does is remove one misleading error conversion so the remaining blocker is visible more honestly:

- previous visible blocker: `GeminiBlankSendTimeout`
- newly exposed blocker: OpenClaw/Gemini path is currently being deferred by `auto_blocked:cloudflare` during send

That is progress, because it narrows the next debugging step to pause/guardian/proxy/browser-state handling instead of Gemini send handoff semantics.
