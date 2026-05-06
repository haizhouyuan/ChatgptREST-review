# 2026-04-25 ChatGPT Frontend 429 Modal Walkthrough v3

## Context

After backend conversation-export 429 mitigation, a human-visible ChatGPT Web popup appeared while the shared Chrome session was open. The user was not actively driving high-volume browser actions, and no new foreground Codex task was expected to be using ChatgptREST.

## Evidence

- `artifacts/mcp_calls.jsonl` showed `chatgpt_web_ask` at `2026-04-25T17:53:25+0800` failing on a visible modal:
  - `modal-conversation-history-rate-limit`
  - pointer events intercepted by the modal while trying to click `#prompt-textarea`
- The driver returned a generic cooldown/TargetClosed-style result, then the same job continued shortly after, which could amplify the provider-side limit.
- `chatgptrest-driver.service` after the later restart showed no new ChatGPT tool calls except the local compatibility probe.
- `chatgptrest-ui-canary.service` only refreshed stale maint-daemon state and did not call the driver.
- `chatgptrest-finbot-commercial-space.service` ran at `18:00`, but its log showed local finbot artifact updates only.

## Root Cause

The driver did not treat ChatGPT's frontend rate-limit modal as a first-class blocked state. The modal surfaced as a Playwright click failure, so the worker/executor path treated it like a transient browser problem instead of a stop-the-world provider/session limit.

## Runtime Mitigation

Paused the automation paths that can touch ChatGPT Web while investigating:

- `chatgptrest-worker-send.service`
- `chatgptrest-worker-wait.service`
- `chatgptrest-driver.service`
- `chatgptrest-ui-canary.timer`
- `chatgptrest-health-probe.timer`
- ChatGPT-related finbot/planning timers that could submit work later

## Code Fix

- Driver now detects `modal-conversation-history-rate-limit` from DOM selectors and Playwright error text.
- Driver writes `blocked_state.reason=frontend_rate_limit` with a default cooldown of at least one hour.
- `chatgpt_web_ask` returns `ChatGPTFrontendRateLimit` instead of generic transient cooldown when the modal is observed during send.
- Executor preflight maps `frontend_rate_limit` to `blocked`, not retryable `cooldown`.
- Repair gate treats `ChatGPTFrontendRateLimit` as an external prerequisite and blocks autofix/clear-blocked loops.

## Verification Plan

- Targeted unit tests for driver modal classification, executor preflight mapping, and repair gate denial.
- Syntax compile for changed Python modules.
- GitNexus detect changes before commit.
- Closeout wrapper after commit.
