# 2026-04-04 GPT Pro Thought Guard Thinking Heavy Retry Fix Walkthrough v1

## What I Investigated

The user reported that recent GPT Pro conversations were returning short answers without a visible thinking trace, and those cases should have triggered a retry.

I traced the chain through:

- `chatgptrest/executors/chatgpt_web_mcp.py`
- `chatgpt_web_mcp/_tools_impl.py`
- `chatgptrest/worker/worker.py`
- recent live `artifacts/jobs/*/result.json` and `events.jsonl`

## What I Found

### 1. Executor-side thought guard only covered `pro_extended`

The current guard condition was effectively:

- run thought guard only when `preset == pro_extended`

But live jobs were mostly using:

- `preset = thinking_heavy`

So the guard was simply not running on the actual preset in use.

### 2. The live failing jobs really had no thinking trace

Sample jobs:

- `77a75f06bf464afb90232d97e2ed7199`
- `d83c6e1170514f1197b016a6b9346d22`
- `f33a7ee306104b7a9e0492cf32026a31`
- `402a2fe87e144c23aac827ae7af78fca`

These all had:

- short answers
- `thinking_observation = null`
- `completion_guard_completed_under_min_chars`
- `canonical_answer.ready = false`

### 3. Worker-side regenerate logic exists, but it did not catch these cases

`chatgptrest/worker/worker.py` can route some suspicious Pro answers to `needs_followup_regenerate`, but these sampled answers were being classified as `final` by `_classify_answer_quality()`. That meant they later got handled by `min_chars` downgrade logic instead.

I checked whether to fix this inside global `classify_answer_quality()`, but GitNexus reported `CRITICAL` blast radius for that function, so I deliberately avoided that route.

## What I Changed

I kept the fix local to `chatgptrest/executors/chatgpt_web_mcp.py`:

- added shared thought-guard preset set:
  - `pro_extended`
  - `thinking_extended`
  - `thinking_heavy`
- added a narrow helper that flags:
  - completed answer
  - conversation URL present
  - answer shorter than `min_chars`
  - no `Thought for ...` trace / no usable `thinking_observation`
- reused the existing `chatgpt_web_regenerate` same-thread path

## Why This Fix Is Better

It fixes the live regression without changing global answer-quality classification behavior for unrelated surfaces.

In other words:

- narrow blast radius
- keeps same-thread regenerate behavior
- matches the user’s expected product behavior
- avoids broad export / API view regressions

## Verification I Ran

- `python3 -m py_compile chatgptrest/executors/chatgpt_web_mcp.py tests/test_chatgpt_thought_guard_regenerate.py`
- `./.venv/bin/pytest -q tests/test_chatgpt_thought_guard_regenerate.py tests/test_thought_guard_require_thought_for.py`
- `./.venv/bin/pytest -q tests/test_executor_pro_fallback.py tests/test_chatgpt_web_answer_rehydration.py tests/test_worker_and_answer.py::test_completion_guard_routes_suspicious_pro_short_answer_to_regenerate_followup tests/test_public_agent_pro_regenerate_guard.py`

## Note

`apply_patch` remained broken in this environment (`No such file or directory` on both absolute and repo-relative targets), so I had to use minimal in-repo file rewrite commands for this patch. Code was re-verified with `py_compile` and targeted pytest after each change.
