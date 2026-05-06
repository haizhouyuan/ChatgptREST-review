# Pro Research Thinking Trace Guard v1

Date: 2026-04-27

## Incident

The user reported another ChatGPT Pro conversation with no visible Pro thinking:

```text
https://chatgpt.com/c/69ef4413-99bc-83e8-959c-9e7b8dd54345
```

The matching job was:

```text
job_id: c887b531770743539bc079c81c7d0261
status: completed
phase: wait
answer_chars: 4521
created: 2026-04-27 19:09:44 CST
updated: 2026-04-27 19:12:55 CST
```

## Evidence

The job did not fail model selection:

```text
export_last_assistant_model_slug=gpt-5-5-pro
export_last_assistant_thinking_effort=extended
export_last_assistant_finish_type=stop
export_last_assistant_is_complete=true
```

But the browser-side observation did not prove the thinking path:

```text
model_observed.model_text=ChatGPT
model_observed.thinking_time=null
model_observed.thinking_time_requested=extended
```

The previous guard did run once at send timeout:

```text
completion_guard_downgraded
reason=thinking_send_timeout_without_complete_export
answer_chars=4520
min_chars_required=4000
```

Later conversation export reconciled the answer as final because the backend message was complete and the answer exceeded `min_chars`.

## Root Cause

The prior fix only fail-closed completed Pro/thinking answers when both were true:

1. the answer was below `min_chars`;
2. no usable `Thought for ...` / `thinking_observation` trace existed.

This incident was longer than `min_chars`:

```text
answer_chars=4520
min_chars_required=4000
```

So the missing thinking trace was treated as acceptable once backend export showed `gpt-5-5-pro` and `thinking_effort=extended`.

That was the wrong finality contract for external review. For high-value Pro/research/review jobs, model metadata proves the selected lane, but it does not prove the visible high-reasoning path happened. The system must fail closed when the thinking path is missing, even if the text is long enough.

## Fix

`ChatGPTWebMcpExecutor` now has a second thought-guard class:

```text
missing_thought_for_research_answer
```

It triggers when all are true:

- preset is `pro_extended`, `thinking_extended`, or `thinking_heavy`;
- job completed;
- a conversation URL exists;
- params match the research/review contract (`deep_research`, research/review purpose, or Pro/thinking preset with `min_chars >= 1200`);
- the answer is non-empty;
- no usable thinking trace is observed.

Default toggle:

```text
CHATGPTREST_THOUGHT_GUARD_REQUIRE_TRACE_FOR_RESEARCH=1
```

When triggered, the existing same-thread repair path is reused:

- if `chatgpt_web_regenerate` returns `completed`, the regenerated answer replaces the degraded one;
- if it returns `in_progress`, `queued`, `cooldown`, or `blocked`, that non-completed state is adopted so the worker continues waiting;
- if regenerate is unavailable or fails unexpectedly, the job returns `needs_followup` with `error_type=ThoughtGuardMissingTrace`.

## Why This Is Still Narrow

This does not globally require visible thinking for every Pro message. It applies to research/review contracts where the caller asked for substantial Pro evidence.

Short operational prompts and compact follow-ups remain governed by the older short-answer guard and optional strict mode:

```text
CHATGPTREST_THOUGHT_GUARD_REQUIRE_THOUGHT_FOR=0
```

## Tests

Regression coverage was added for the exact missed shape:

- a Pro review answer of 4520 characters, `min_chars=4000`, no thinking trace, now triggers same-thread regenerate;
- the same answer with `thinking_observation.thought_for_present=true` is accepted;
- existing short-answer regenerate and fail-closed behavior remains intact.

Validation commands:

```text
python3 -m py_compile chatgptrest/executors/chatgpt_web_mcp.py chatgptrest/executors/config.py tests/test_chatgpt_thought_guard_regenerate.py tests/test_thought_guard_require_thought_for.py
./.venv/bin/pytest -q tests/test_chatgpt_thought_guard_regenerate.py tests/test_thought_guard_require_thought_for.py
```

## Operational Lesson

Do not equate `gpt-5-5-pro + thinking_effort=extended + finish_type=stop` with acceptable Pro review evidence.

For high-value Pro external review, the finality contract is now:

```text
correct model lane
+ complete assistant message
+ content contract
+ usable thinking-path evidence
```

If the last condition is missing, ChatgptREST should repair or fail closed rather than silently accepting a possibly instant Pro answer.
