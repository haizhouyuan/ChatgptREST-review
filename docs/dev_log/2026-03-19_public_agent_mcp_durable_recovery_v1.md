# Summary

Hardened the public agent MCP recovery path so `chatgptrest-mcp` can recover more like a product surface instead of a best-effort wrapper.

This change addresses the first takeover priority from the `2026-03-19_codex_handoff_session_summary_v2.md` handoff:

- public MCP now honors API auto-start / retry on local transport faults
- deferred agent watches survive MCP restart as durable state
- `advisor_agent_status` can auto-resume a missing watch from persisted state + durable `/v3/agent/session/{session_id}`
- transport-recovered long/deferred turns reattach a background watch instead of returning a bare recovered session

# Problem

Before this patch, the public MCP path had two structural gaps:

1. `chatgptrest-mcp.service` exported `CHATGPTREST_MCP_AUTO_START_API=1`, but `chatgptrest/mcp/agent_mcp.py` did not implement the auto-start / retry logic that already existed in the legacy admin MCP. A local API restart or transient `Connection refused` still surfaced as a hard failure.

2. Public agent watch state lived only in `_AGENT_WATCH_STATE` / `_AGENT_WATCH_TASKS` process memory.

That meant:

- API session state was durable on the `/v3/agent/session/{session_id}` side
- MCP watch state was not
- after MCP restart, long deferred sessions still existed, but the “background watch” experience had to be manually reconstructed

This was the exact gap called out in handoff v2 section 5.2 / 5.3.

# Fix

## 1. Public MCP now has the same local API auto-start semantics

In [agent_mcp.py](/vol1/1000/projects/ChatgptREST/chatgptrest/mcp/agent_mcp.py):

- added `_open_with_recovery(...)`
- added `_maybe_autostart_api_for_base_url(...)`
- reused shared control-plane helpers from `chatgptrest.core.control_plane`

All public MCP HTTP calls that matter here now use the recovery wrapper:

- `_session_status(...)`
- `_wait_stream_terminal(...)`
- `advisor_agent_turn(...)`
- `advisor_agent_cancel(...)`
- `advisor_agent_status(...)`

Effect:

- local transport failure can trigger one API auto-start attempt
- request is retried on the same MCP call path
- coding agents are less likely to bypass back to `/v1/jobs` because of a small MCP/API flap

## 2. Deferred watch state is now durable

Added a small file-backed `_AgentWatchStore` in [agent_mcp.py](/vol1/1000/projects/ChatgptREST/chatgptrest/mcp/agent_mcp.py).

Resolution order:

- sibling of `CHATGPTREST_AGENT_SESSION_DIR` if configured
- sibling of `CHATGPTREST_DB_PATH` if configured
- pytest temp dir in tests
- fallback `/tmp/chatgptrest-agent-mcp-watch`

Persisted fields include the current:

- `watch_id`
- `session_id`
- `watch_status`
- `stream_url`
- `timeout_seconds`
- `notify_done`
- `last_status`
- terminal `result_session` when available

## 3. `advisor_agent_status` now auto-resumes a lost watch

On `advisor_agent_status(session_id)`:

- restore persisted watch metadata if in-memory watch is gone
- query durable API session state
- if the session is still non-terminal, auto-resume the watch
- if the session is already terminal, mark the restored watch terminal too and persist the recovered terminal state

This turns the durable API session into the source of truth and lets MCP rebuild the watcher view after restart.

## 4. Transport-recovered deferred turns now reattach watch state

If `advisor_agent_turn(...)` loses the HTTP response after the API accepted a long/deferred turn:

- it still recovers via `/v3/agent/session/{session_id}`
- and now also resumes/reattaches a background watch for that same session

So the client gets:

- stable `session_id`
- `transport_recovered=true`
- background watch metadata again

# Tests

Ran:

```bash
./.venv/bin/pytest -q tests/test_agent_mcp.py tests/test_bi09_mcp_business_pass.py
```

Added focused coverage for:

- transport failure triggering public MCP API auto-start retry
- persisted watch state being restored and used for auto-resume after module reload
- transport-recovered deferred turns reattaching a background watch

# Scope

This patch does **not** restart services yet.

It only closes the code/test gap for handoff step 1 on the public agent MCP path. The next operational priorities remain:

1. wait-phase cancel faster terminalization
2. cc-sessiond orphan/test pool cleanup
3. strategist main task rerun and strategist chain completion
