# 2026-04-26 Client Usage Watch 6h v1

## Context

The user asked for a six-hour watch after repeated ChatGPT Pro / ChatGPT Web 429 and automation-channel issues. The watch goal was not to block ChatGPT Web by default. The goal was to keep client usage working, detect real client-impacting failures quickly, and intervene only when the evidence showed an operational problem.

This watch followed earlier fixes for:

- backend conversation export 429 hidden by DOM fallback;
- frontend rate-limit modal classification;
- manual Pro hold durability and systemd masking;
- wrapper error contract for MCP 429/cooldown responses.

## Window

- Start: `2026-04-26 02:02:01 +0800`
- End: `2026-04-26 08:02:01 +0800`
- Duration: `21600` seconds
- Samples: `360`
- Monitor artifacts:
  - `artifacts/monitor/client_usage_watch_6h/20260425T180201Z/summary.json`
  - `artifacts/monitor/client_usage_watch_6h/20260425T180201Z/samples.jsonl`
  - `artifacts/monitor/client_usage_watch_6h/20260425T180201Z/alerts.jsonl`

## Operating Rule

The watch used a client-first posture:

- Do not submit new ChatGPT Web work from the monitor.
- Do not set a global hold merely because the monitor is running.
- Keep API and public MCP reachable so clients receive structured errors instead of connection failures.
- Keep driver/send/wait available unless there is a confirmed client-impacting failure.
- Prefer DB/event inspection over automation calls.
- Restart or unmask units only if the runtime is already broken or a stale protection artifact is blocking clients.

## Findings

### Stable Client Surface

Throughout the watch:

- `chatgptrest-api.service` stayed `active`.
- `chatgptrest-mcp.service` stayed `active`.
- `chatgptrest-driver.service` stayed `active`.
- `chatgptrest-worker-send.service` stayed `active`.
- `chatgptrest-worker-wait.service` stayed `active`.
- `chatgptrest-manual-pro-watch-guard.service` stayed `inactive`.
- Runtime masks stayed empty.
- The web-automation allow file stayed present.

No automatic remediation actions were taken during the six-hour monitor window.

### No 429 Recurrence Observed

The watch did not observe a new ChatGPT frontend 429/cooldown event, Cloudflare block, or global frontend-rate-limit hold. It also did not observe a new manual Pro guard recurrence or a new systemd mask blocking client usage.

### Client Job Issues Found

Two Pro jobs were worth tracking during the early part of the watch:

- `c45a1105c7a44bdaad606a33c78bfc4d` initially showed short-confirmation behavior, then completed with `completion_quality=final` and `answer_chars=18926`.
- `a8dd0ce6a1b74d60aff7918b249da36f` hit `TargetClosedError` and then a short confirmation retry event. The retry loop recovered without a service restart, and the job completed with `completion_quality=final` and `answer_chars=15323`.

These were real client-usage concerns, but they did not justify restarting the driver because active services were healthy and a restart would have risked interrupting the same client workflow.

### Historical Queue State

The remaining active counts were stale `needs_followup` jobs, not live in-flight failures. During the watch, the counts did not grow; some decreased:

- `chatgpt_web.ask needs_followup/wait` decreased from `18` to `17`.
- `gemini_web.ask needs_followup/send` decreased from `2` to `1`.
- `gemini_web.ask needs_followup/wait` stayed at `1`.

This does not require emergency automation. Cleanup should be a separate maintenance task so it does not re-open old ChatGPT Web work during client usage.

## Root Cause Reflection

The earlier failure pattern was not one isolated 429 bug. It was a control-plane ownership problem:

- the same shared ChatGPT Web session was used both by human Pro browsing and automation;
- multiple agents could submit, resume, export, clear pauses, or restart services independently;
- degraded success paths could hide rate limits;
- soft runtime holds were treated as operational convention instead of durable invariants;
- monitoring initially produced evidence but did not convert that evidence into a timely client-protection decision.

The systemic fix therefore cannot be only another retry or cooldown patch. The important invariant is explicit ownership of the ChatGPT Web channel:

- human-owned manual Pro windows require a durable provider-specific hold;
- client-owned automation windows require the hold to be released explicitly and the services to remain reachable;
- monitoring must distinguish those states and avoid turning observation into a new outage.

## Outcome

For this six-hour client-usage watch:

- no new 429 recurrence was observed;
- no client-blocking service failure was observed;
- no manual guard/mask recurrence was observed;
- no automatic action was needed;
- two early Pro job retry/short-answer concerns recovered to final answers without disruptive intervention.

## Residual Work

- Keep stale `needs_followup` cleanup separate from client-facing incident response.
- Promote the six-hour watch query shape into a reusable monitor that reports event uniqueness, not repeated alerts from the same event window.
- Keep using explicit release semantics for manual Pro holds; do not let another agent clear pause/stop a guard as a substitute for release.
- Add a client-facing status summary that separates `blocked_by_policy`, `provider_cooldown`, `browser_retrying`, and `service_down` so clients know whether to wait, retry later, or switch provider.
