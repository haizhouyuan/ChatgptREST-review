# 2026-04-26 ChatGPT Web Pro Channel Systemic RCA v1

## Incident Chain

This was not one isolated `HTTP 429` bug. The visible symptoms were frontend 429 modals, short Pro acknowledgements, stuck external-review evidence, canceled jobs that still produced ChatGPT conversations, and duplicate Pro review submissions. The common dependency was the same shared ChatGPT Web browser session.

After the six-hour client watch ended at `2026-04-26 08:02:01 +0800`, the next client window showed:

- `3a7bad9c1a0e44428f411d392670577d`: canceled at `10:31:57`, but `artifacts/mcp_calls.jsonl` later showed a real ChatGPT conversation at `10:32:49`.
- `f1f3a58df8044549bd9238a96b7ee710`: valid Labebe Pro job, completed with `25938` answer chars.
- `12b446044b9247aea196aae2b03c044a`: duplicate of `f1f3a58...`, canceled at `10:43:40`, but still reached driver and created another ChatGPT conversation at `10:44:08`.
- `928d48e393514ef29054eaab49dcae7a`: corrected Paperclip Pro replacement, completed with `15174` answer chars.
- `536754fc7ab2474dad499c3a3b65c3f3`: later Pro job, completed with `23718` answer chars.

No new Cloudflare/frontend-rate-limit hold was observed in this post-watch slice. The client-visible problem was upstream of a new 429: too many ChatGPT Web side effects were still allowed to reach one shared Pro browser lane.

## Root Cause

The root cause was a broken ownership boundary around ChatGPT Web:

- Admission control trusted `internal-submit-wrappers` too much. It had HMAC identity, but no ChatGPT-specific single-flight limit until the first fix, and duplicate prevention was path-sensitive rather than content-aware.
- Idempotency only protected the exact request hash. A client could submit the same prompt/packet again with a new idempotency key and still create another job.
- Cancellation was treated as if it could abort provider side effects. In reality, once the worker entered `ChatGPTWebMcpExecutor.run(...)`, the send call was inside `asyncio.to_thread(self._client.call_tool, ...)`. `task.cancel()` stopped the worker's result path, but it did not kill the thread or undo the browser send.
- Observability split after in-flight cancel: DB said `canceled/send` with no conversation URL, while `artifacts/mcp_calls.jsonl` proved that the provider had created a conversation.

The earlier 429/export fixes were necessary but incomplete. They handled rate-limit classification after the browser/API had already been stressed. The missing invariant was admission-time protection before new ChatGPT Web side effects are allowed.

## Systemic Fix

Implemented changes:

- Low-level ask duplicate fingerprints now use readable attachment content identity: filename, size, and SHA-256. Restaging the same packet in a different allowed directory no longer bypasses dedupe.
- Attachment content fingerprinting is prepared before the `/v1/jobs` DB write transaction, so hashing a review packet does not extend the SQLite `BEGIN IMMEDIATE` lock window.
- `internal-submit-wrappers` and `planning-wrapper` now have `max_in_flight_by_kind.chatgpt_web.ask = 1`. This keeps the shared ChatGPT Web Pro lane single-flight per registered wrapper while preserving Gemini/non-ChatGPT options under the client-wide limit.
- Duplicate detection now runs before concurrency checks, so repeated equivalent work returns `409 low_level_ask_duplicate_recently_submitted` with `existing_job_id` instead of a less useful generic 429.
- Worker in-flight send cancellation now waits for the already-started executor to return, records `inflight_send_cancel_observed`, `inflight_send_cancel_completed`, and `inflight_send_cancel_recorded`, persists any observed `conversation_url`, then finalizes the job as canceled.
- Runbook and client registry docs now describe the new 409/429 contracts and client behavior.

## Expected Behavior After Fix

- Same prompt plus same packet content, even under different staging dirs, is rejected as a recent duplicate.
- A second low-level ChatGPT Web ask from the same wrapper is rejected while the first is queued or in progress.
- Canceling after provider send has started no longer creates a silent split between DB state and driver evidence. The job remains canceled, but the provider-side conversation URL is captured if available.
- Clients get structured errors that tell them whether to reuse an existing job, wait, or switch provider.

## Residual Boundaries

This still does not make browser send physically abortable. Python cannot kill a running `to_thread` call safely, and ChatGPT cannot unsend a prompt that has already reached the composer. The correct invariant is therefore:

- prevent duplicate/competing jobs at admission;
- keep cancellation honest once provider send starts;
- never use a new idempotency key or new staging directory as a retry strategy for the same Pro work.

## Validation

Targeted validation:

```bash
PYTHONPATH=. ./.venv/bin/pytest -q tests/test_low_level_ask_guard.py
PYTHONPATH=. ./.venv/bin/pytest -q tests/test_worker_and_answer.py::test_chatgpt_send_cancel_preserves_inflight_provider_evidence
PYTHONPATH=. ./.venv/bin/pytest -q tests/test_worker_and_answer.py
```
