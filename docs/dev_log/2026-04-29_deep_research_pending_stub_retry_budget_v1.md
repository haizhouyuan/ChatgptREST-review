# Deep Research Pending Stub Retry Budget Fix

Date: 2026-04-29

## Incident

Job `bde24a8adec8418180c939b9fde954d4` successfully reached ChatGPT:

- `prompt_sent` was recorded.
- `conversation_url` was set to `https://chatgpt.com/c/69f17856-e968-83e8-a69e-5f1ff2334488`.
- The conversation export contained a 258-character Deep Research status card:
  `# HomePC LLM 本地部署路线 / Update / ... / Researching`.

The worker selected that export text as a final-quality assistant candidate, then completion guard downgraded it because it was below `min_chars=800`. Each wait poll then consumed normal browser retry budget. After four polls, the job failed closed as `needs_followup` with `WebRetryBudgetExceeded`.

## Root Cause

Two independent guardrails were individually reasonable but wrong in combination:

1. `_deep_research_export_should_finalize(...)` recognized Deep Research acknowledgements and connector stubs, but did not recognize the newer visible `Update ... Researching` status card.
2. Once completion guard converted the short status card back to `in_progress`, wait persistence treated the poll like a normal browser-visible retry instead of a long-running Deep Research pending state.

This made a legitimate long-running Deep Research job look like a repeated failed browser retry.

## Fix

- Added `_deep_research_is_progress_stub(...)` and `_deep_research_pending_wait_reason(...)`.
- `Update ... Researching` and equivalent Chinese pending markers no longer finalize export answers.
- Pending Deep Research output sets `deep_research_pending_wait` metadata and uses `CHATGPTREST_DEEP_RESEARCH_PENDING_RETRY_AFTER_SECONDS` for slower polling.
- Wait persistence now records `wait_deep_research_pending_observed` and releases the job without consuming normal browser retry budget.
- `wait_deep_research_pending_observed` is classified as non-progress for the no-progress guard; the first visible status-card text is still captured by `wait_partial_answer_progressed`, but repeated sightings cannot keep a dead job alive forever.

## Verification

Targeted regression:

```bash
PYTHONPATH=. ./.venv/bin/pytest -q \
  tests/test_worker_and_answer.py::test_wait_phase_deep_research_progress_stub_does_not_burn_browser_retry_budget \
  tests/test_worker_and_answer.py::test_wait_phase_deep_research_uses_longer_timeout \
  tests/test_worker_and_answer.py::test_worker_fail_closes_when_browser_retry_budget_exceeded
```

Broader related tests:

```bash
python3 -m py_compile chatgptrest/worker/worker.py
PYTHONPATH=. ./.venv/bin/pytest -q tests/test_min_chars_completion_guard.py tests/test_deep_research_response_envelope.py tests/test_deep_research_export_guard.py tests/test_conversation_export_missing_reply_policy.py
PYTHONPATH=. ./.venv/bin/pytest -q tests/test_worker_and_answer.py
```

## Operational Note

This does not auto-complete short Deep Research status cards. It keeps the original job waiting with slower cadence and leaves the existing Deep Research no-progress timeout as the fail-closed boundary.
