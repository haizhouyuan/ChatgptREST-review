# 2026-04-04 Gemini idempotency get restore walkthrough v1

## Summary

While narrowing `W1`, live driver calls to `gemini_web_idempotency_get` failed with:

- `Error executing tool gemini_web_idempotency_get: name '_idempotency_lookup' is not defined`

That meant the executor's idempotency recovery path existed in code but was dead in runtime.

## Actions

1. confirmed the live tool failure through the driver MCP surface
2. inspected [`chatgpt_web_mcp/providers/gemini/ask.py`](/vol1/1000/projects/ChatgptREST/chatgpt_web_mcp/providers/gemini/ask.py)
3. found `_idempotency_lookup` referenced but not imported into that module namespace
4. added the missing import
5. added a direct regression test
6. restarted `chatgptrest-driver.service`
7. re-ran live `gemini_web_idempotency_get` lookup against the failed job key

## Outcome

The tool now returns real idempotency records. This gave a harder live diagnosis for the current Gemini send failure:

- not a recovered thread URL
- not a silent dedupe artifact
- a real runtime-side crash signature (`Target crashed`) with `sent=false`

## Scope boundary

This walkthrough records only the idempotency-get restore batch. It does not freeze the later `maint_daemon/ui_canary` contention diagnosis or the `GEMINI_REUSE_EXISTING_CDP_PAGE` runtime A/B as completed work.
