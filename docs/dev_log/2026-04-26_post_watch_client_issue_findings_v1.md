# 2026-04-26 Post-Watch Client Issue Findings v1

## Context

After the six-hour client usage watch ended at `2026-04-26 08:02:01 +0800`, the user asked what had happened since monitoring stopped. The review window for this note is `08:02:01` through approximately `10:49 +0800`.

The investigation was read-first and did not submit new ChatGPT Web work. One runtime action was taken: canceling a queued/send duplicate job after an equivalent earlier job had already reached wait phase.

## Findings

### Services Stayed Up

At inspection time:

- `chatgptrest-api.service`: active
- `chatgptrest-mcp.service`: active
- `chatgptrest-driver.service`: active
- `chatgptrest-worker-send.service`: active
- `chatgptrest-worker-wait.service`: active
- `chatgptrest-manual-pro-watch-guard.service`: inactive

No new frontend 429, Cloudflare block, DB frontend-rate-limit cooldown, or manual Pro hold recurrence was observed in this window.

### Rejected Submits

There were two `POST /v1/jobs` `403 Forbidden` responses:

- `2026-04-26 10:30:03`
- `2026-04-26 10:35:48`

The later successful request metadata says the first 403 was caused by original `toyresearch` attachment paths outside the ChatgptREST allowed upload roots, and another failed attempt was caused by `replayed_hmac_nonce`. No job was created for those failed submits.

### Canceled Job Still Reached Driver

Job `3a7bad9c1a0e44428f411d392670577d` was created at `10:31:15` and canceled at `10:31:57` with the explicit reason that local pre-Pro review found a runtime-evidence wording defect in the Kimi artifact.

The DB final state is `canceled/send`, but `artifacts/mcp_calls.jsonl` shows the underlying `chatgpt_web_ask` still completed at `10:32:49` with:

- conversation URL: `https://chatgpt.com/c/69ed790d-a500-83e8-8349-5286dd3bbe10`
- `answer_chars=79`

This means canceling an in-flight send stops the worker result path, but it cannot abort a blocking driver call that has already entered `asyncio.to_thread(...)`.

### Duplicate Pro Submits

Two nearly identical Labebe radical design brainstorm jobs were created:

- `f1f3a58df8044549bd9238a96b7ee710`
- `12b446044b9247aea196aae2b03c044a`

The first job had already reached wait phase with conversation URL `https://chatgpt.com/c/69ed7b7b-8c14-83e8-86db-e1fc1280843d`. The second job was canceled with an explicit `duplicate_pro_submission` reason to avoid another ChatGPT Web send.

However, the same in-flight cancellation limitation occurred: `artifacts/mcp_calls.jsonl` still shows job `12b446...` sent and created `https://chatgpt.com/c/69ed7bc2-0250-83e8-a39b-8f87aaa583c4`, returning only a short `79` character acknowledgement.

### Additional Paperclip Pro Replacement

Job `928d48e393514ef29054eaab49dcae7a` was then submitted with a corrected v2 Paperclip review packet. It entered wait phase with conversation URL `https://chatgpt.com/c/69ed7c2c-e948-83e8-9496-5f421fd4773b` and initially produced another short acknowledgement (`84` chars), so it remained in wait for completion guard recovery.

## Root Cause

This was not a service-down incident. It was a duplicate-submission and cancellation-boundary incident:

- `internal-submit-wrappers` had no runtime `dedupe_window_seconds` or `max_in_flight_jobs` limits, even though other wrappers such as `planning-wrapper` already did.
- Different idempotency keys were enough to create equivalent Pro jobs with the same prompt and attachments.
- Worker cancellation is cooperative only up to the boundary before the driver call starts. Once the executor is inside the blocking driver call running in a thread, `task.cancel()` does not kill that thread or undo a prompt already being sent in the browser.

## Fix Applied

`ops/policies/ask_client_registry.json` now gives `internal-submit-wrappers`:

- `max_in_flight_jobs=2`
- `dedupe_window_seconds=1800`

This preserves limited concurrency for independent client work while blocking equivalent duplicate low-level asks for 30 minutes.

Regression coverage was added in `tests/test_low_level_ask_guard.py` to verify that two equivalent `chatgptrest_chatgpt_ask_submit` requests with different idempotency keys are rejected with `low_level_ask_duplicate_recently_submitted`.

## Validation

```bash
PYTHONPATH=. ./.venv/bin/pytest -q tests/test_low_level_ask_guard.py
./.venv/bin/python scripts/check_doc_obligations.py --diff HEAD --json
```

## Residual Risk

Cancel remains best-effort after a driver call starts. Preventing duplicate sends before claim/driver entry is therefore the important protection layer. A deeper future fix would require passing an abortable cancel signal into the driver layer itself or splitting send into smaller cancellable phases.
