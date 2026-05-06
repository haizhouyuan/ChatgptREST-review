# 2026-04-10 Web Retry Human Pacing Guard v1

## Why

ChatGPT Web / Gemini Web jobs can trigger anti-abuse controls when retries happen at machine-like cadence.
We found multiple browser-visible retry paths still using `5s`, `12s`, `20s`, `30s`, or `60s` defaults.

This created two classes of risk:

- repeated visible web actions that are faster than normal human behavior
- inconsistent retry pacing across worker, ChatGPT Web send cooldowns, and Gemini send/wait paths

## What Changed

Added a central fail-safe policy in `chatgptrest/core/web_retry_policy.py`:

- `CHATGPTREST_WEB_HUMAN_RETRY_FLOOR_SECONDS` default `90`
- `CHATGPTREST_WEB_HUMAN_RETRY_JITTER_MAX_SECONDS` default `15`

Browser-visible retry paths now respect that floor even if a narrower per-flow knob is configured lower.

Covered paths:

- worker infra/UI cooldowns
- worker wait-phase infra/UI cooldowns
- completion-guard requeue cooldowns
- ChatGPT unsent transient send cooldown
- Gemini inline send retry delay
- Gemini wait transient retry-after
- ChatGPT send-stage `in_progress` revisit delay when no thread URL is available yet
- ChatGPT `Answer now / Writing code` revisit delay

## Result

The system now fails safe on retry pacing:

- existing higher values like `120s` or `180s` are preserved
- lower values are raised to at least `90s`
- small jitter prevents exact robotic repetition

This does not change low-level local retry loops that are not user-visible browser actions.

## Validation

Targeted tests:

- `tests/test_worker_and_answer.py`
- `tests/test_gemini_infra_retry.py`
- `tests/test_gemini_send_exception_retry.py`

Also update:

- `ops/systemd/chatgptrest.env.example`
- `docs/runbook.md`
- `chatgptrest/core/env.py`
