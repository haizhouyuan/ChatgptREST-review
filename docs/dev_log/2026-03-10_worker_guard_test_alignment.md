# 2026-03-10 Worker Guard Test Alignment

## Context
- `tests/test_rescue_followup_guard.py` assumed an intentional follow-up should finalize even if the executor returned a placeholder-short answer (`follow-answer`).
- `tests/test_worker_and_answer.py::test_completion_guard_still_enforces_min_chars_for_short_answers` assumed the `min_chars` guard would fire before the answer-quality guard even when the answer text was only three characters long.

## What Changed
- Updated the rescue follow-up test to return a substantive multi-sentence final answer so it still proves the intended behavior: parent-completed follow-ups are executed normally instead of being short-circuited.
- Updated the min-chars worker test to use a semantically complete but under-length answer so it exercises the `min_chars` branch rather than the earlier `answer_quality_suspect_short_answer` branch.

## Why
- Current production behavior is correct: the answer-quality guard runs before the `min_chars` guard and should continue blocking placeholder-short outputs.
- The stale tests were asserting older ordering assumptions, which created false failures during reduced/full suite runs.

## Validation
- `./.venv/bin/pytest -q tests/test_rescue_followup_guard.py -vv`
- `./.venv/bin/pytest -q tests/test_worker_and_answer.py -k "completion_guard or followup"`
- `./.venv/bin/python -m py_compile tests/test_worker_and_answer.py tests/test_rescue_followup_guard.py`
