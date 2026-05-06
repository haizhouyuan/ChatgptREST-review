# 2026-04-10 ChatGPT Wait Thread Contamination Guard v1

## Problem

A `chatgpt_web.ask` deep-research job stayed in `phase=wait` and requeued dozens of times on the
same `conversation_url`. The visible ChatGPT Web symptom was `Too many requests`.

Observed evidence on the live job:

- repeated `wait_requeued`
- repeated `completion_guard_downgraded`
- stable `conversation_url`
- `conversation.json` showed the matched user turn had **no assistant reply after it**, while the
  same thread already contained later unrelated `user` turns

This means the worker was treating a reused/contaminated conversation as if it were still safely
waitable.

## Root Cause

The completion-time export path only distinguished:

- export lag with no reply yet
- substantial DOM answer present, so ignore the missing export reply

It did **not** distinguish the more dangerous case where:

- the export matches the current user turn
- another `user` turn appears before any assistant reply for that turn

In that state, continuing to `wait_requeue` the same thread can hammer ChatGPT Web and trigger
rate-limit / unusual-activity protection.

## Fix

### Export helper

`extract_answer_from_conversation_export_obj()` now records:

- `next_role_after_match`
- `subsequent_user_turn_count`
- `thread_contaminated_after_match`

when the matched user turn is followed by another `user` turn before any assistant reply.

### Worker completion guard

`_should_downgrade_when_export_missing_reply()` now fail-closes when export metadata indicates
thread contamination, even if the DOM answer is substantial.

Worker behavior now becomes:

- emit `completion_guard_thread_contaminated`
- project `completion_guard.action=needs_followup`
- stop waiting on the current thread instead of looping through
  `completion_guard_downgraded -> wait_requeued`

## Tests

Validated with:

```bash
PYTHONPATH=. .venv/bin/pytest -q \
  tests/test_conversation_export_missing_reply_policy.py \
  tests/test_longest_candidate_extraction.py \
  tests/test_worker_and_answer.py::test_completion_guard_fails_closed_when_export_thread_is_contaminated \
  tests/test_e2e.py -q
```

## Operator Note

This fix prevents future wait-loop storms on contaminated ChatGPT threads, but it does not
retroactively clean up already-running jobs. Any already-looping job should be canceled or allowed
to settle after the worker restart.
