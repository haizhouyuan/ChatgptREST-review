# 2026-04-04 Gemini Auto-Blocked Pause Unblock Review v1

## Summary

This batch fixes a narrow but production-visible mismatch in the OpenClawBot planning live path:

- ChatGPT blocked-state auto-pause (`auto_blocked:cloudflare`) should still defer ChatGPT send jobs.
- The same auto-pause must not stall Gemini planning jobs on unrelated lanes.

The bug existed in two places:

1. job creation / defer (`pause_filter_allows_job`)
2. worker claim SQL (`claim_next_job`)

Both are now narrowed so Gemini send jobs can continue during a ChatGPT-only auto-blocked pause, while manual pauses and ChatGPT deferral semantics remain unchanged.

## Code Changes

### 1. Create-time pause filter

File: `chatgptrest/core/pause.py`

- Added provider-aware carve-out for `reason.startswith("auto_blocked:") and provider_id == "gemini"`.
- This keeps the existing repair-job exemption intact.
- Manual `send` / `all` pauses still apply.

### 2. Worker claim path

File: `chatgptrest/core/job_store.py`

- Extended `_build_claim_where(...)` with `auto_blocked_pause`.
- Worker-side claim SQL now allows `kind LIKE 'gemini_web.%'` only when the active pause is an `auto_blocked:*` pause.
- `claim_next_job(...)` computes `auto_blocked_pause` directly from live pause state and passes it into the shared WHERE builder.

### 3. Regression tests

Files:
- `tests/test_ops_endpoints.py`
- `tests/test_pause_queue.py`

Added coverage for both sides of the bug:

- create-time defer: ChatGPT deferred, Gemini not deferred
- worker claim: ChatGPT skipped, Gemini claimable

## Evidence

### Automated verification

Passed:

```bash
python3 -m py_compile chatgptrest/core/job_store.py chatgptrest/core/pause.py tests/test_pause_queue.py tests/test_ops_endpoints.py
./.venv/bin/pytest -q \
  tests/test_pause_queue.py::test_pause_send_skips_send_phase_non_repair_jobs \
  tests/test_pause_queue.py::test_pause_send_allows_wait_phase_when_no_repair \
  tests/test_pause_queue.py::test_pause_all_allows_only_repair \
  tests/test_pause_queue.py::test_auto_blocked_pause_allows_gemini_send_claims \
  tests/test_ops_endpoints.py::test_ops_pause_get_set_and_job_deferred \
  tests/test_ops_endpoints.py::test_auto_blocked_pause_still_defers_chatgpt_but_not_gemini
```

### Live evidence

Before the fix, fresh Gemini planning jobs were stuck at:

- `status=queued`
- `phase=send`
- `lease_owner=None`
- `attempts=0`

under a global pause with:

- `mode=send`
- `reason=auto_blocked:cloudflare`

After API + send-worker reload with the new code:

- `343cb71a4485417896a71050625deb6f` was claimed by `YogaS2:3058854`
- `31390d9e1382464ca3a5eb574593ec32` was then also claimed by the same send worker

This proves the worker-side claim gate was the remaining blocker after the API-side defer fix.

## Remaining blocker

This batch does **not** make the Gemini live lane green. It only removes the false global pause gate.

The latest live evidence still shows a real provider/send-path failure for at least one claimed job:

- job: `343cb71a4485417896a71050625deb6f`
- result: `GeminiBlankSendTimeout`
- fail-closed event: `blank_gemini_cooldown_fail_closed`

So the current W1 state is now more precise:

- `claim` is unblocked
- `send` can still fail inside the Gemini provider lane

## Independent Judgment

This was the correct narrow fix to make before touching provider internals.

Without it, the system mixed two different failure layers:

1. false global pause interference
2. real Gemini send-path instability

Now these layers are separated, which makes the next provider-focused debugging step much cleaner.
