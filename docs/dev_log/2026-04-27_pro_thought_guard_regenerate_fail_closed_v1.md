# Pro Thought Guard Regenerate Fail-Closed v1

Date: 2026-04-27

## Scope

Follow-up fix for the ChatGPT conversation:

```text
https://chatgpt.com/c/69ef1df6-38b8-83e8-8dea-5e8348d05d9a
```

This extends `docs/dev_log/2026-04-27_pro_min_chars_and_contract_projection_rca_v1.md`.

## Finding

The earlier RCA fixed completion-state projection and min-chars terminalization, but it did not fully cover the user's observed behavior:

- The first automated Pro answer used the correct Pro metadata.
- The answer still did not visibly enter a useful Pro thinking path.
- The user manually clicked `retry with 5.5 pro`.
- The manual retry then visibly triggered Pro thinking and produced a better run.

The job event stream already contained the important signal:

```text
thought_guard_abnormal
reason=missing_thought_for_short_answer
action=regenerate_skipped
require_thought_for=false
```

So the system recognized the degraded Pro run, but it treated the guard as diagnostic instead of fail-closed evidence.

## Root Cause

`ChatGPTWebMcpExecutor` had a one-shot same-thread regenerate path for Pro/thinking short answers missing a `Thought for ...` observation.

The bug was in the handling of non-completed regenerate results:

1. If `chatgpt_web_regenerate` returned `completed`, the executor used the regenerated answer.
2. If it returned anything else, including `in_progress`, the executor marked the action as `regenerate_skipped`.
3. The original short answer stayed as `completed` and flowed to worker completion guards.

That is wrong for exactly this incident. A regenerate that returns `in_progress` means the manual retry path has started and the worker should wait. It is not a skipped repair. If regenerate fails or is unavailable, the original short no-thinking Pro answer is not acceptable final evidence and should become `needs_followup`.

## Fix

`ChatGPTWebMcpExecutor` now distinguishes three outcomes after thought guard abnormality:

- `completed`: use the regenerated answer.
- `in_progress` / `queued` / `cooldown` / `blocked`: adopt the regenerate result and return that non-completed state to the worker.
- unavailable / failed / unexpected: fail closed to `needs_followup` for `missing_thought_for_short_answer`.

The fail-closed result preserves the original short answer as provisional evidence and records:

```text
error_type=ThoughtGuardMissingTrace
_thought_guard.fail_closed=true
_thought_guard.fail_closed_reason=missing_thought_for_short_answer
```

## Why This Is Narrow

This does not globally require visible `Thought for ...` for every Pro answer. The fail-closed default is scoped to completed Pro/thinking answers that are already suspicious because they are below `min_chars` and have no usable thinking observation.

That preserves normal short/compact prompts while blocking the high-value review failure mode that caused shallow Pro evidence to slip through.

## Tests

Added coverage in `tests/test_chatgpt_thought_guard_regenerate.py`:

- short Pro answer without thinking trace adopts regenerate `in_progress` instead of treating it as skipped;
- short Pro answer without thinking trace returns `needs_followup` when regenerate cannot start;
- existing successful-regenerate behavior remains unchanged.

Validation:

```text
python3 -m py_compile chatgptrest/executors/chatgpt_web_mcp.py tests/test_chatgpt_thought_guard_regenerate.py
./.venv/bin/pytest -q tests/test_chatgpt_thought_guard_regenerate.py tests/test_thought_guard_require_thought_for.py
```

## Operational Lesson

Correct model metadata is not enough. For high-value Pro/research asks, a short answer without thinking evidence is a quality/finality fault even when the backend says the assistant message has `finish_type=stop`.

The system should either move into the same-thread regenerate/wait path or fail closed. It must not silently accept the first shallow answer as completed external review evidence.
