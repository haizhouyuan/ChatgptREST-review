# 2026-04-25 chatgptrest_call MCP 429 Error Contract Walkthrough v1

## Context

During the Multica chief sidecar workflow, `skills-src/chatgptrest-call/scripts/chatgptrest_call.py` was used to submit a ChatGPT Pro architecture-advisor packet. The wrapper failed with a local `JSONDecodeError` and no `job_id`.

A direct `automation_ask` retry showed the real condition: ChatGPT Web frontend cooldown was active and the public MCP path returned HTTP `429` with `chatgpt_frontend_rate_limit_active`, `reason=frontend_rate_limit`, and `retry_after_seconds`.

## Root Cause

`_decode_tool_result(...)` assumed every text item in an MCP `tools/call` response was JSON:

```python
parsed = json.loads(text)
```

If the MCP layer returned a plain-text tool error containing the real HTTP 429/cooldown detail, the wrapper raised `JSONDecodeError`. That hid the actionable error contract from the calling agent.

## Fix

- Added structured parsing for non-JSON MCP text responses.
- Preserved a safe `raw_text_preview`.
- Extracted common cooldown fields when present:
  - `http_status`
  - `error`
  - `reason`
  - `retry_after_seconds`
  - embedded JSON error body as `parsed_error`
- Updated automation error output so agent-mode failures include a structured `detail` object instead of only `JSONDecodeError`.

## Verification

```bash
PYTHONPATH=. ./.venv/bin/python -m py_compile \
  skills-src/chatgptrest-call/scripts/chatgptrest_call.py \
  tests/test_skill_chatgptrest_call.py

PYTHONPATH=. ./.venv/bin/pytest -q \
  tests/test_skill_chatgptrest_call.py \
  tests/test_skill_chatgptrest_call_coding_agent_v1.py

scripts/check_doc_obligations.py --diff HEAD --json
```

Observed result:

- py_compile: passed
- targeted pytest: `20 passed`
- doc obligations: `ok=true`

## Boundary

This does not bypass ChatGPT frontend cooldown and does not retry Pro automatically. It only makes the wrapper fail with the true cooldown reason so callers can schedule retry, choose a degraded secondary advisor lane, or no-op without losing the root cause.
