# 2026-04-07 Gemini Deep Think `quota_info` Error Fix v1

## What changed

- Fixed `chatgpt_web_mcp/providers/gemini/ask.py` so `gemini_web_ask_pro_deep_think()` initializes `quota_info` before entering the main send/response `try` block.
- Added provider-level regression coverage in [tests/test_gemini_deep_think_error_path.py](/vol1/1000/projects/ChatgptREST/tests/test_gemini_deep_think_error_path.py).

## Why

The external dual-model review run for Gemini Deep Think failed before producing any review content. Job artifacts showed:

- initial retries surfacing `DictModel` validation noise at the MCP layer
- final terminal cause surfacing `name 'quota_info' is not defined`

The local root cause was an exception path inside `gemini_web_ask_pro_deep_think()` that referenced `quota_info` without guaranteed initialization. That turned a recoverable provider/tool failure into an internal crash in the Gemini lane itself.

## Validation

Ran:

```bash
./.venv/bin/pytest -q \
  tests/test_gemini_deep_think_error_path.py \
  tests/test_gemini_deep_think_overloaded.py
```

Result: `6 passed`

## Impact

- This is a narrow provider-level reliability fix.
- It does not change Deep Think routing, preset selection, or fallback policy.
- It restores a valid dict-shaped terminal result on the affected exception path so upper layers can classify and surface the failure correctly.
