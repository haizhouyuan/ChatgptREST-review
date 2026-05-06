# 2026-04-11 Web Retry Budget Guard v1

## Context

`ChatGPT Web` and `Gemini Web` browser-facing retries were already paced with a human-like retry floor, but that alone did not stop multi-minute worker storms when one loop family kept scheduling more visible retries. This left operators with two gaps:

- no provider-level dashboard showing that one web provider was becoming "hot"
- no proactive fail-close before the site itself returned `Too many requests`

## Problem

Repeated browser-visible retries could still accumulate within a short rolling window even when each individual retry respected the 90s floor. The system needed a second line of defense:

- per-job retry budget
- per-provider retry budget
- observable hot state before hard exceed
- fail-close semantics when the budget is exhausted

## Change

Added `chatgptrest.core.web_retry_budget` and wired it into the worker/browser retry path.

New env knobs:

- `CHATGPTREST_WEB_RETRY_BUDGET_WINDOW_SECONDS` default `900`
- `CHATGPTREST_WEB_RETRY_BUDGET_MAX_PER_JOB` default `4`
- `CHATGPTREST_WEB_RETRY_BUDGET_MAX_PER_PROVIDER` default `12`
- `CHATGPTREST_WEB_RETRY_BUDGET_WARN_RATIO` default `0.8`

New events:

- `browser_retry_scheduled`
- `browser_retry_budget_exceeded`

New fail-close behavior:

- browser-visible retry budget exceed now terminates the loop as:
  - `status=needs_followup`
  - `last_error_type=WebRetryBudgetExceeded`

New operator visibility:

- additive fields on `/v1/ops/status`
- dedicated `/v1/ops/retry-budget`

## Scope Notes

This budget counts only retries that would schedule another visible browser action. It is intentionally narrower than generic internal retry accounting.

It does not rewrite historical `wait_requeued` / `completion_guard_downgraded` events into the new budget family; the new guard is forward-looking and designed to prevent future storms.

## Verification

Targeted tests:

- `tests/test_worker_and_answer.py::test_worker_fail_closes_when_browser_retry_budget_exceeded`
- `tests/test_ops_endpoints.py::test_ops_retry_budget_surfaces_hot_provider_and_recent_counts`

Broader regression:

- `tests/test_worker_and_answer.py`
- `tests/test_ops_endpoints.py`
- `tests/test_e2e.py`

## Operational Guidance

- Treat `retry_budget_hot` as an early warning, not a signal to immediately loosen thresholds.
- Treat `retry_budget_exceeded` as "the platform prevented a web-visible storm from continuing."
- Fix the underlying loop family first; raise thresholds only after confirming the retries are genuinely human-paced recovery behavior.
