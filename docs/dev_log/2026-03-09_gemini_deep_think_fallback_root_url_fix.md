# 2026-03-09 Gemini Deep Think Fallback Root URL Fix

## Problem

`GeminiDeepThinkToolNotFound` was still reproducible in live traffic even though the
executor already had a "fallback to Pro" path.

Historical failing job:

- `745d655c2f8c4d2c9486d230f1c70654`

The failing Deep Think attempt returned `conversation_url=https://gemini.google.com/app`.
That value is a Gemini landing page, not a stable thread. The fallback path was
passing it into `gemini_web_ask_pro`, which could poison the fallback by trying to
continue on a non-thread page.

## Fix

File:

- `chatgptrest/executors/gemini_web_mcp.py`

Change:

- Deep Think fallback now only reuses `conversation_url` when it is a stable Gemini
  thread URL (`/app/<thread_id>`).
- Base `/app` URLs are dropped before the Pro fallback call.

Test:

- `tests/test_gemini_deep_think_overloaded.py`
  - `test_deep_think_tool_not_found_falls_back_to_pro`
  - asserts the Pro fallback does **not** inherit the base `/app` URL

## Live verification

Post-fix live job:

- `23289ac2f1594ca6b8417db16e19b2d2`

Observed result:

- reached `phase=wait`
- stable Gemini thread URL set:
  - `https://gemini.google.com/app/733e36c1d3133fe6`
- did not reproduce `GeminiDeepThinkToolNotFound`

## Ledger note

Based on `live verified => mitigated`, the issue family:

- `iss_8df4c2d2da5f44c79cd9cfa88ec4b801`
- `iss_10d53fdd435e49a7abbcb5d382f361ff`

can remain `mitigated` and should only move to `closed` after three qualifying client
successes without recurrence.
