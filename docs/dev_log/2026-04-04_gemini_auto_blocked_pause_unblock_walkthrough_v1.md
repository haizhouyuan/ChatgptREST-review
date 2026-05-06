# 2026-04-04 Gemini Auto-Blocked Pause Unblock Walkthrough v1

## What I did

1. Verified that fresh `gemini_web.ask` planning jobs were no longer being deferred at creation time after the earlier API-side pause carve-out.
2. Confirmed they still were not being claimed by the send worker.
3. Traced the second blocker to `chatgptrest/core/job_store.py`, where claim SQL still treated the pause as global.
4. Added a narrow worker-side carve-out: only `gemini_web.%` jobs may bypass `auto_blocked:*` pauses.
5. Added regression tests for both create-time defer and worker-side claim behavior.
6. Restarted the live send worker and verified that previously stuck Gemini jobs were finally claimed.
7. Read live artifacts to separate the next blocker: `GeminiBlankSendTimeout` still happens after claim.

## Why this change is narrow

- It does not weaken manual pause semantics.
- It does not bypass `pause_all` for arbitrary providers.
- It does not touch repair-job behavior.
- It only corrects the current overreach of ChatGPT blocked-state auto-pause into Gemini planning jobs.

## What changed in live behavior

Before:

- fresh Gemini planning jobs stayed `queued/send` forever under `auto_blocked:cloudflare`
- no worker lease
- no attempts increment

After:

- fresh Gemini planning jobs are claimable
- attempts move to `1`
- worker lease is present
- provider-level outcome is now visible

## What is still not solved

- The Gemini provider/send lane can still fail with `GeminiBlankSendTimeout`.
- This batch does not make W1 green by itself.
- The next step must inspect Gemini send/attachment/runtime evidence, not pause routing.
