# 2026-04-25 ChatGPT Frontend Submit Gate Walkthrough v5

## Context

During a manual three-hour Pro watch, the browser-visible ChatGPT rate-limit state recurred even after backend export 429 cooldown handling and driver-side frontend modal blocking were added.

The important new observation was that other coding-agent sessions could still submit fresh `chatgpt_web.ask` jobs through the public MCP automation surface while the user was manually using Pro. Those jobs caused `chatgptrest-worker-send.service`, `chatgptrest-worker-wait.service`, and `chatgptrest-driver.service` to restart and reach the ChatGPT Web driver. Driver preflight then blocked with `frontend_rate_limit`, but by that point the runtime had already started browser automation again.

## Incident Evidence

- Manual monitor directory: `artifacts/monitor/manual_pro_watch/20260425_191035/`
- `alerts.jsonl` recorded:
  - unexpected `chatgptrest-worker-send.service`, `chatgptrest-worker-wait.service`, and `chatgptrest-driver.service` activity at 19:33-19:41 CST
  - `chatgpt_web_ask`, `chatgpt_web_wait`, and `chatgpt_web_conversation_export` calls from jobs created by other clients
- Confirmed submitted jobs:
  - `1f4578ec01b941f590232ff33def6fe5`
  - `34d3743473bc45cea150a30c9670c7a5`
  - `864cc458f7b4450c8f7a156dff0a4096`
  - `4a906781912a4c3d9fa54de9b8981eb0`
  - `c97eba7bc8cc42e89de666ea8331f5db`
- Those jobs were canceled during the watch to protect the shared ChatGPT browser session.

## Root Cause

The previous frontend-rate-limit fix was driver/repair scoped:

- driver returned `ChatGPTFrontendRateLimit`
- driver wrote `blocked_state.reason=frontend_rate_limit`
- repair skipped UI probes/actions

That was necessary but incomplete. The submit layer still accepted new `chatgpt_web.ask` jobs. A new job could therefore enqueue, wake workers, and start the driver before the driver-level block had a chance to stop the action. This is the same class of problem as the earlier export 429 issue: a downstream layer knew the shared session was unsafe, but the upstream submit layer still allowed more work to enter the system.

## Fix

Added a narrow `/v1/jobs` submit gate for new `chatgpt_web.ask` jobs:

- checks DB cooldown key `chatgpt_web_frontend_rate_limit`
- optionally checks `CHATGPTREST_CHATGPT_FRONTEND_BLOCK_STATE_FILE` or `CHATGPTREST_DRIVER_STATE_DIR/chatgpt_blocked_state.json`
- rejects new `chatgpt_web.ask` submissions with HTTP 429 while active
- returns `Retry-After`, `blocked_until`, `source`, and `job_created=false`
- preserves idempotent replays for an already-created job
- does not block Gemini submissions or non-ChatGPT job kinds

## Runtime Mitigation During Watch

The monitoring session also applied temporary runtime controls:

- stopped and condition-gated `chatgptrest-driver.service`, `chatgptrest-worker-send.service`, and `chatgptrest-worker-wait.service`
- canceled active/queued browser-Web jobs that would continue touching the shared browser
- seeded `state/driver/chatgpt_blocked_state.json` with a frontend-rate-limit hold
- seeded DB cooldown key `chatgpt_web_frontend_rate_limit`
- ran a lightweight guard loop that killed directly spawned driver/worker processes not managed by the gated services

These runtime controls are operational containment, not the permanent code fix.

## Verification

- `python -m py_compile chatgptrest/api/routes_jobs.py tests/test_chatgpt_frontend_submit_gate.py`
- `pytest -q tests/test_chatgpt_frontend_submit_gate.py`
- `pytest -q tests/test_jobs_write_guards.py tests/test_low_level_ask_guard.py`

## Follow-up Risk

The monitor showed at least one direct `python -m chatgptrest.worker.worker --role send --once` process launched outside the standard systemd services. Service-level masks are not sufficient for manual Pro-use protection. Future hardening should add a documented operator pause mode that combines submit gate, worker claim gate, and visible runtime status instead of relying on ad hoc service controls.
