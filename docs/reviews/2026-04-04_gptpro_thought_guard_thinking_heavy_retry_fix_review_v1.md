# 2026-04-04 GPT Pro Thought Guard Thinking Heavy Retry Fix Review v1

## Summary

This patch fixes a live regression where recent GPT Pro jobs using `preset=thinking_heavy` could return short, no-trace answers without triggering the existing same-thread regenerate path.

## What Was Wrong

Two conditions combined to bypass the intended retry behavior:

1. `chatgptrest/executors/chatgpt_web_mcp.py` only enabled the executor-side thought guard for `preset == pro_extended`.
2. Recent live jobs were primarily using `preset=thinking_heavy`, and their results frequently had no `thinking_observation` while still returning short answers.

As a result, those jobs skipped executor-side regenerate and later fell into worker-side `completed_under_min_chars` handling instead of `needs_followup_regenerate`.

## Live Evidence

Recent `thinking_heavy` jobs showed this pattern:

- `77a75f06bf464afb90232d97e2ed7199`
- `d83c6e1170514f1197b016a6b9346d22`
- `f33a7ee306104b7a9e0492cf32026a31`
- `402a2fe87e144c23aac827ae7af78fca`

Common traits:

- `params.preset = thinking_heavy`
- `answer_chars` between roughly `100-400`
- `result.json.thinking_observation = null`
- `completion_contract.answer_state = provisional`
- `completion_guard_completed_under_min_chars` event present

These jobs did not take the regenerate path even though they matched the user-visible failure mode: short answer, no visible reasoning trace.

## Code Change

Changed file:

- `chatgptrest/executors/chatgpt_web_mcp.py`

Behavioral change:

- Extend executor-side thought guard coverage from only `pro_extended` to all thinking/pro presets:
  - `pro_extended`
  - `thinking_extended`
  - `thinking_heavy`
- Add an explicit abnormal case for:
  - completed answer
  - same-thread conversation available
  - answer shorter than `min_chars`
  - missing `Thought for ...` trace / missing `thinking_observation`

When these conditions align, executor now triggers the existing same-thread `chatgpt_web_regenerate` flow instead of letting the short answer silently fall through.

## Tests

New regression test:

- `tests/test_chatgpt_thought_guard_regenerate.py`

Verified existing related tests still pass:

- `tests/test_thought_guard_require_thought_for.py`
- `tests/test_executor_pro_fallback.py`
- `tests/test_chatgpt_web_answer_rehydration.py`
- `tests/test_worker_and_answer.py::test_completion_guard_routes_suspicious_pro_short_answer_to_regenerate_followup`
- `tests/test_public_agent_pro_regenerate_guard.py`

## Risk

Blast radius was intentionally kept narrow.

I did **not** modify global `classify_answer_quality()` because GitNexus reported `CRITICAL` upstream impact. The fix stays inside the ChatGPT executor, which GitNexus rated `LOW` risk.

## Expected Outcome

For GPT Pro / `thinking_heavy` jobs, short answers with no visible reasoning trace should now retry on the same conversation via regenerate instead of being accepted into the weaker `completed_under_min_chars` path.
