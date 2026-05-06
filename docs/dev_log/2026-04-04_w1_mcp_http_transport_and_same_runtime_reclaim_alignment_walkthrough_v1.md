# 2026-04-04 W1 MCP HTTP Transport and Same-Runtime Reclaim Alignment Walkthrough v1

## What I did

1. Read the latest live worker journal and confirmed Gemini send attempts were repeatedly failing with `SSE stream timeout (deadline exceeded)`.
2. Checked the current MCP HTTP client behavior and found that `McpHttpClient.call_tool()` always retried once with a fresh session for any `McpHttpError`.
3. Tightened that behavior so deadline-bound stream timeouts do not get replayed through a fresh session.
4. Added targeted tests for:
   - no fresh-session retry on deadline timeout
   - keep fresh-session retry for transport-establishment errors
   - same-runtime blank Gemini idempotency reclaim
5. Restarted the send worker and observed the next live Gemini job on the new code path.

## Why I changed it

The problem was not just “Gemini is slow”. The transport stack was also reissuing certain timed-out calls in a way that could nearly double how long one failing send occupied the pipeline. That made W1 evidence slower and less interpretable.

## What changed in behavior

After this batch:

1. deadline-exceeded MCP tool calls are no longer replayed once more via forced fresh session;
2. session reset retry still exists for connection/session-establishment style failures;
3. ChatgptREST-owned Gemini blank in-progress records can be reclaimed in the same runtime after a short bounded window.

## What did not change

1. Gemini live completion is still not green.
2. The provider can still end in no-thread timeout-style failure.
3. This batch narrows the blocker; it does not remove the blocker.

## Verification run

- `python3 -m py_compile chatgptrest/integrations/mcp_http_client.py tests/test_mcp_http_error_propagation.py`
- `./.venv/bin/pytest -q tests/test_mcp_http_error_propagation.py tests/test_driver_idempotency_upload_hash.py tests/test_gemini_provider_timeout_budget.py`
- follow-up broader regressions run after the transport change before commit

## Current takeaway

The live problem is now even more clearly a provider completion problem, not a generic MCP session retry problem.
