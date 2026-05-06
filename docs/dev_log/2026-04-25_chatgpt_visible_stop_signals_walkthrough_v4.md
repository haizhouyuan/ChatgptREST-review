# ChatGPT Visible Stop Signals Walkthrough v4

Date: 2026-04-25

## Incident Class

The earlier backend export `HTTP 429` fix handled one degraded-success path: backend export could be rate-limited while DOM fallback still returned an answer. The follow-up browser popup showed a broader class:

- ChatGPT Web can expose a visible stop signal in the DOM or Playwright error text.
- If only the send path recognizes that signal, other UI tools can still treat it as a transient error or health probe failure.
- Status probes are safe; UI-touching probes are not safe while the shared browser session is actively rate-limited.

## Root Cause Generalization

`modal-conversation-history-rate-limit` must be handled as a provider/session limit, not as a browser automation failure. The risky paths are any action that opens or manipulates ChatGPT Web:

- send / wait resume
- conversation export when it uses the UI
- self-check and capture-ui canaries
- refresh and regenerate repair actions
- repair/autofix `clear_blocked`, `capture_ui`, `refresh`, `regenerate`

## Fix

This version makes the frontend rate-limit state stop-the-world across ChatGPT UI actions:

- `frontend_rate_limit` blocked state no longer allows `self_check` or `capture_ui` probe actions.
- Shared exception handling maps frontend rate-limit modal evidence to `status=blocked` and `ChatGPTFrontendRateLimit` for wait, export, self-check, capture-ui, refresh, and regenerate.
- Repair check/autofix skip ChatGPT UI probes and UI repair actions when the driver blocked status reports `frontend_rate_limit`.
- The contract/runbook now state that only status-only probes are allowed during this blocked state.

## Runtime Guidance

When this state is active:

- leave send/wait/driver/timers paused unless a human intentionally resumes them after cooldown;
- use only `chatgpt_web_blocked_status` or the blocked-state file for confirmation;
- do not use `clear_blocked` as a shortcut unless a human has verified the browser session has recovered.

## Verification Plan

- Compile changed modules.
- Run focused tests for driver blocked-state handling, executor error mapping, repair gate, and repair autofix.
- Run worker/autofix tests that cover no-regression for recoverable runtime failures.
- Run doc obligation check and GitNexus detect_changes before commit.
