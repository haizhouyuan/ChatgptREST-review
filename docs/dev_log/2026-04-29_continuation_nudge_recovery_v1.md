# Continuation Nudge Recovery

Date: 2026-04-29

## Incident

The ChatGPT conversation `https://chatgpt.com/c/69f190ae-cd68-83e8-b3a4-2f3e782e4401` was tied to job `fc30512340bb496cb1428b75bcb26540`.

Timeline:

- 13:01 CST: job created and prompt sent.
- 13:42 CST: export saw a later user message: `我看你卡住了，好久没进度，一直是reading documents，请继续`.
- The worker classified this as `ConversationThreadContaminated` and moved the job to `needs_followup`.
- 13:56 CST: the job was explicitly canceled as superseded by a resubmission.
- Later, the same ChatGPT web conversation produced a final answer in the browser.

## Root Cause

The finality guard treated every user message after the matched request as contamination. That is correct for a real new request or scope change, but too strict for a human/operator continuation nudge whose only purpose is to tell the same in-flight model run to continue.

The old logic stopped scanning the matched assistant window at the first subsequent user message. Because of that, it never considered the later 18,236-character final assistant answer, even though the later user message was a narrow "please continue" nudge rather than a new task.

## Recovery

A one-off read-only conversation export was run after the job had already been canceled. It did not send a new prompt. The export grew from 43 KB to 668 KB and contained a final assistant answer.

Recovered artifact:

```text
artifacts/jobs/fc30512340bb496cb1428b75bcb26540/answer.recovered_after_cancel.md
artifacts/jobs/fc30512340bb496cb1428b75bcb26540/recovered_after_cancel_meta.json
```

The recovered answer is not marked as the canonical completed job result because the job was already canceled. It is evidence that the browser-visible final answer existed and that the guard was overly strict for this nudge pattern.

## Fix

`chatgptrest.core.conversation_exports.extract_answer_from_conversation_export_obj(...)` now distinguishes:

- benign continuation nudges: short messages such as `continue`, `please continue`, `卡住了，请继续`, `好久没进度，请继续`;
- real contamination: a substantive second user turn that changes scope, switches mode, adds another project, or otherwise changes the requested work.

When all subsequent user turns after the matched request are benign continuation nudges, extraction continues scanning later assistant messages and can select the final answer. The match info records:

- `subsequent_user_turn_count`;
- `continuation_nudge_count`;
- `thread_contaminated_after_match=false`.

Substantive second user turns still remain contaminated and fail closed.

## Verification

Tests:

- `tests/test_conversation_export_reconcile.py::test_extract_answer_allows_benign_continuation_nudge_after_match`
- `tests/test_conversation_export_reconcile.py::test_extract_answer_keeps_substantive_second_user_turn_contaminated`
- `tests/test_conversation_export_reconcile.py`
- `tests/test_longest_candidate_extraction.py`
- `tests/test_worker_and_answer.py -k 'conversation_export or export_missing_reply or active_finalization or deep_research_progress_stub'`
