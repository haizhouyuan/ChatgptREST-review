# 2026-04-04 Gemini MCP Stream Timeout Alignment Review v1

## Summary

This batch aligns loopback MCP SSE socket timeout with the caller deadline for long-lived Gemini sends.

The live evidence that motivated it is unusually direct:

- fresh OpenClawBot live jobs progressed past the old `page_slot` dead-occupancy issue after driver restart
- the latest live Gemini send then failed at `prepare_prompt`
- `run_meta.elapsed_seconds` was `60.024` seconds
- `chatgptrest/integrations/mcp_http_client.py` was still capping loopback SSE socket timeout at `60s`

That means the transport layer could still cut off a slow-but-legitimate local MCP stream before the job-level Gemini deadline.

## Code Change

File: `chatgptrest/integrations/mcp_http_client.py`

Changed `_jsonrpc_post_stream(...)` from a hard `min(timeout_sec, 60.0)` cap to:

```python
socket_timeout_sec = max(60.0, min(float(timeout_sec), 180.0))
```

Effect:

- short requests still keep a conservative lower bound
- long loopback SSE requests can now use the caller deadline up to `180s`
- we stop force-cutting every long-lived local provider call at `60s`

## Test Coverage

File: `tests/test_mcp_http_error_propagation.py`

Added coverage proving that a long loopback SSE request keeps the extended socket timeout instead of being truncated to `60s`.

## Why this is safe

- Change scope is local to loopback MCP stream POST handling.
- GitNexus upstream impact for `_jsonrpc_post_stream` is `LOW`.
- The ceiling stays bounded at `180s`; this is not an unlimited socket hold.
- The change aligns transport timeout with job-level provider deadlines instead of silently contradicting them.

## Live diagnosis context

This batch does not by itself prove W1 green. It removes one strong candidate for the remaining Gemini live send instability.

Current W1 interpretation after this batch:

1. false global auto-block pause interference has already been fixed
2. dead Gemini page-slot occupancy has been cleared by runtime restart
3. the next likely truncation point was the local MCP SSE `60s` socket cap

The next live rerun after worker reload is the decisive validation.
