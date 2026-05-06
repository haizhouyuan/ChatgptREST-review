# 2026-04-04 Gemini idempotency get restore review v1

## What changed

This batch restores the live `gemini_web_idempotency_get` tool so the Gemini executor can use idempotency lookup for send/wait recovery instead of silently losing that path at runtime.

## Code changes

1. [`chatgpt_web_mcp/providers/gemini/ask.py`](/vol1/1000/projects/ChatgptREST/chatgpt_web_mcp/providers/gemini/ask.py)
   - explicitly imports `_idempotency_lookup` from `chatgpt_web_mcp.idempotency`
   - fixes the live `NameError: _idempotency_lookup is not defined` in `gemini_web_idempotency_get(...)`
2. [`tests/test_gemini_idempotency_get.py`](/vol1/1000/projects/ChatgptREST/tests/test_gemini_idempotency_get.py)
   - adds a direct regression test for the tool path

## Why this matters

The Gemini executor already has recovery logic that asks the driver for idempotency records after send-path churn. In live runtime that tool was broken, so the executor always failed open to an empty recovery result.

This change does **not** declare `W1` done. It only restores a recovery primitive that had silently regressed.

## Verification

Passed:

```bash
python3 -m py_compile chatgpt_web_mcp/providers/gemini/ask.py tests/test_gemini_idempotency_get.py
./.venv/bin/pytest -q tests/test_gemini_idempotency_get.py
```

Live verification after driver restart:

- `gemini_web_idempotency_get` no longer throws `name '_idempotency_lookup' is not defined`
- for job `752fa0dbc1b044018a8cf31cab3acc39`, the driver now returns a real record showing:
  - `status=cooldown`
  - `sent=false`
  - `conversation_url=https://gemini.google.com/app`
  - `error=Error: Locator.count: Target crashed`

## Current interpretation

Restoring this tool narrowed the current live Gemini failure surface further:

- some blank-send cases are not merely missing recovery wiring
- at least one current live case is a real driver/runtime crash before stable thread evidence exists

So this patch is necessary infrastructure, but not the final `W1` fix.
