# 2026-03-17 Agent Streaming And Thought Guard Defaults Walkthrough v1

## Scope

This change set closes two follow-up items on the public advisor-agent surface:

1. Enable the ChatGPT Pro thought guard by default so suspicious instant answers
   trigger same-conversation regenerate without requiring a manual VNC click.
2. Add deferred agent delivery plus SSE session streaming so clients can submit
   a turn, get a `session_id` immediately, and observe status/result updates
   without blocking a foreground coding-agent tool call.

## Code Changes

### 1. Thought-guard defaults

- `chatgptrest/executors/config.py`
  - `CHATGPTREST_THOUGHT_GUARD_MIN_SECONDS` default changed from `0` to `300`
  - `CHATGPTREST_THOUGHT_GUARD_AUTO_REGENERATE` default changed from `false` to `true`
- `chatgptrest/core/env.py`
  - environment registry default for `CHATGPTREST_THOUGHT_GUARD_AUTO_REGENERATE`
    changed to `True` so runtime config and env inventory stay aligned

### 2. Public agent deferred delivery + SSE

- `chatgptrest/api/routes_agent_v3.py`
  - added `delivery_mode=deferred|background|async` support on `POST /v3/agent/turn`
  - deferred mode now returns `202` with `session_id`, `stream_url`, and delivery metadata
  - added `GET /v3/agent/session/{session_id}/stream`
  - added in-memory session event buffering for `turn.submitted`, session lifecycle,
    and terminal `done` emission
  - exposed `stream_url` on sync responses and session status responses
- `chatgptrest/mcp/agent_mcp.py`
  - `advisor_agent_turn` now forwards `delivery_mode`

## Test Coverage

Added/updated tests:

- `tests/test_thought_guard_require_thought_for.py`
  - verifies default min-seconds / auto-regenerate behavior
- `tests/test_routes_agent_v3.py`
  - verifies deferred turn returns `202`
  - verifies SSE stream emits terminal `done` with completed session payload
- `tests/test_agent_mcp.py`
  - verifies MCP forwards `delivery_mode=deferred`

Executed:

```bash
/vol1/1000/projects/ChatgptREST/.venv/bin/python -m py_compile \
  chatgptrest/api/routes_agent_v3.py \
  chatgptrest/mcp/agent_mcp.py \
  chatgptrest/executors/config.py \
  chatgptrest/core/env.py \
  tests/test_routes_agent_v3.py \
  tests/test_agent_mcp.py \
  tests/test_thought_guard_require_thought_for.py

/vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q \
  tests/test_thought_guard_require_thought_for.py \
  tests/test_routes_agent_v3.py \
  tests/test_agent_mcp.py

/vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q \
  tests/test_agent_v3_routes.py \
  tests/test_bi14_fault_handling.py \
  tests/test_mcp_server_entrypoints.py
```

## Notes

- `gitnexus_detect_changes()` on this worktree still reported unrelated finbot
  service edits from the main repo baseline, so local `git status` and targeted
  diff review were used as the accurate scope check for this branch.
- The new SSE path is intentionally additive: existing sync `advisor_agent_turn`
  behavior remains the default unless clients opt into `delivery_mode=deferred`.
