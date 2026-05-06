# Pro Thinking Fast Answer And Partial Finality RCA v1

Date: 2026-04-27

## Scope

Investigated Codex session `019dc032-6429-7bd3-821f-c4d53d0c5a37` and ChatgptREST jobs:

- `fce0398f3ec847b194e4cc89fe9cf3ef`
- `d6bfdc79dae94a1aaa4faf5a654a7243`
- `06a8a546d4f0451c804b6e02a5043bd6`
- follow-on corrective job observed: `076c4a2b073b495d87bb93a7d097b12a`

## Findings

The first job was not a model-selection failure. The MCP call used `model=5.2 pro` and `thinking_time=extended`; backend conversation export recorded `gpt-5-5-pro` and `thinking_effort=extended`.

The user-visible concern was real: the first answer completed quickly and felt like a shallow advisor summary. ChatGPT Web can return a completed Pro/extended answer without exposing a separate visible thinking trace. Before this fix, ChatgptREST treated that answer as final because it had enough characters, matched the requested Pro backend metadata, and the export marked the assistant message complete.

The systemic bug appeared on the follow-up path. Job `d6bfd...` was marked `completed` while the backend export still had the matched assistant turn as `in_progress` with no complete assistant text after the follow-up prompt. The worker trusted the DOM answer because it was longer than `min_chars`. The actual assistant turn later reached `finish_type=max_tokens` and produced much more text, proving the earlier artifact was a partial read.

Job `06a8...` then compounded the issue: it was marked `completed` with an answer artifact that was effectively prompt text / stale visible content, while the export still showed a current assistant generation in progress. This was another instance of finality being inferred from DOM text length instead of the current assistant turn's backend completion state.

Runtime factor: the live env had `CHATGPTREST_DEFAULT_SEND_TIMEOUT_SECONDS=60`. Upload and UI setup consumed a significant part of the send-stage budget, leaving only a short model-generation window before the driver returned partial DOM state. The send/wait split is still correct, but finality must fail closed when the export says the current assistant is not complete.

## Root Cause

ChatgptREST had two overly permissive finality paths:

1. `extract_answer_from_conversation_export_obj(...)` did not preserve candidate assistant `status` / `metadata.is_complete` from the export-normalized message list, so an `in_progress` assistant text could be selected as if it were final when it looked structurally complete.
2. `_should_downgrade_when_export_missing_reply(...)` allowed a substantial DOM answer to override a backend export window where the matched user turn was followed by an `in_progress` assistant but no completed assistant reply.

This let a partial Pro/thinking answer become canonical evidence and enabled the next follow-up to be sent while the prior assistant turn was still generating.

## Fix

- Preserve `status`, `metadata.is_complete`, and `finish_details.type` through `conversation_export_messages(...)`.
- Treat a selected candidate from an `in_progress` assistant message as `matched_in_progress_partial`, returning no final answer from export extraction.
- For Pro/thinking/Deep Research jobs, downgrade `matched_but_missing_assistant + next_role_after_match=assistant + export_has_in_progress=true` to in-progress wait instead of accepting DOM length.
- If a thinking preset hit send-stage timeout and no complete export confirms finality, requeue to wait rather than storing an answer artifact.

## Evidence

Local replay after the fix:

- `fce0398...`: remains final because export has `chosen_assistant_status=finished_successfully`, no in-progress assistant, and `thinking_effort=extended`.
- `d6bfdc...`: now downgrades with `matched_assistant_still_in_progress`.
- `06a8a...`: now downgrades with `matched_assistant_still_in_progress`.

Regression coverage:

- `tests/test_longest_candidate_extraction.py`
- `tests/test_conversation_export_missing_reply_policy.py`
- `tests/test_worker_and_answer.py::test_thinking_send_timeout_without_complete_export_requeues_to_wait`

## Operational Lesson

For Pro/thinking jobs, `answer_chars >= min_chars` is not finality evidence when the backend export says the matched assistant turn is still `in_progress`. The canonical finality evidence is the current assistant turn's export status, completion metadata, and finish details.

The first quick answer can still be a valid but low-value model output. That is a separate quality problem from finality. The system should not claim it was a model mismatch when backend metadata proves Pro/extended was used; it should record it as a low-value Pro answer and let caller-side quality review decide whether to ask a sharper same-thread follow-up.
