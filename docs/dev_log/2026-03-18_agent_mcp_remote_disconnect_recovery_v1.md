## Summary

Fixed public agent MCP transport handling so transient `RemoteDisconnected` does not immediately surface as a hard failure to coding agents.

## Problem

- `advisor_agent_turn` posted to `/v3/agent/turn`.
- If the MCP wrapper lost the HTTP response after the API had already accepted the request, clients saw:
  - `ok=false`
  - `error_type=RemoteDisconnected`
- That encouraged unsafe blind retries and could duplicate premium asks.

## Fix

- `advisor_agent_turn` now always sends an explicit `session_id`.
  - If the caller did not provide one, the MCP wrapper generates one client-side.
- On transient transport disconnects (`RemoteDisconnected`, `URLError`), the wrapper now:
  1. queries `/v3/agent/session/{session_id}`
  2. returns the recovered session payload if it already exists
  3. otherwise returns a structured recoverable error with the preserved `session_id`

This keeps the client on the same session contract instead of guessing whether it should retry.

## Tests

Ran:

```bash
./.venv/bin/pytest -q tests/test_agent_mcp.py tests/test_bi09_mcp_business_pass.py
```

Added coverage for:

- transport disconnect followed by successful status recovery
- transport disconnect with no recovered session returning a recoverable error and stable generated `session_id`

## Impact

- Public MCP client behavior is safer for coding agents
- No API contract change required
- No duplicate-submit retry added at transport level
