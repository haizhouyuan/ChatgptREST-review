# 2026-04-25 Manual Pro Watch Guard Systemic Fix v2

## Problem

The first three-hour manual Pro watch was not strict enough. It detected background ChatGPT Web activity, but detection did not immediately become a stop condition. The user had to report the visible 429, which means the watch failed its primary purpose.

The defect was systemic, not just a missing script:

- passive sampling was accepted as monitoring;
- manual ChatGPT Pro use was not represented as a first-class runtime mode;
- new submissions, existing queued jobs, direct export jobs, driver UI actions, and systemd units were controlled by separate partial mechanisms;
- provisional Pro exports were being interpreted too optimistically even when the final answer was missing.

## New Invariant

During a human ChatGPT Pro usage window, ChatGPT Web automation is not degraded; it is forbidden.

The canonical hold reason is:

```text
manual_pro_session
```

This is distinct from provider-side:

```text
frontend_rate_limit
```

Both reasons block ChatGPT Web automation, but `manual_pro_session` is proactive protection and should not be reported as if ChatGPT caused a 429.

## Implementation

- API submit gate now treats `manual_pro_session` as an active ChatGPT Web automation hold.
- API submit gate checks the repo default `state/driver/chatgpt_blocked_state.json` even when no explicit env var points to it.
- Executor preflight treats `manual_pro_session` as blocked, matching `frontend_rate_limit`, captcha, Cloudflare, and verification states.
- `ops/manual_pro_watch_guard.py` is the active guard for manual Pro windows:
  - seeds `state/driver/chatgpt_blocked_state.json` with `reason=manual_pro_session`;
  - sets DB pause `mode=all`, `reason=auto_blocked:manual_pro_watch_guard`;
  - watches protected systemd units;
  - watches active `chatgpt_web.%` jobs;
  - watches new `chatgpt_web_*` tool calls in `artifacts/mcp_calls.jsonl`;
  - stops driver/send/wait immediately on violation and returns non-zero.
- `ops/systemd/chatgptrest-manual-pro-watch-guard.service` records the operational service contract.

## Why This Is Systemic

The fix is not relying on one observer to notice a log line. It creates layered enforcement:

- submit layer: new ChatGPT Web jobs are rejected with `job_created=false`;
- queue layer: worker claim is paused for ChatGPT Web work by DB pause;
- executor layer: driver preflight returns blocked before prompt send;
- process layer: protected driver/send/wait units are stopped if they come alive;
- evidence layer: every violation writes JSONL evidence and a non-zero guard result.

## Residual Policy

When the user is actively using Pro manually:

- do not start driver/send/wait;
- do not clear `manual_pro_session` until the user explicitly ends the window;
- do not cite provisional Pro exports as final external evidence;
- prefer non-ChatGPT providers only when the task does not require ChatGPT Pro Web specifically.
