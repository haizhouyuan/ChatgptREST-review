# 2026-03-18 public agent session persistence v1

## Problem

`/v3/agent/*` kept session state only in process memory.

That meant:

- `advisor_agent_status(session_id=...)` returned `session_not_found` after API restart
- SSE `/v3/agent/session/{session_id}/stream` lost prior session history on restart
- long-running public agent sessions were not durable enough for CC / Codex / Antigravity

## Scope

This change keeps the public agent facade contract intact and only replaces the
backing store used by:

- `agent_turn`
- `get_session`
- `stream_session`
- `cancel_session`

## Implementation

### 1. Added a file-backed session store

New module:

- `chatgptrest/api/agent_session_store.py`

It persists:

- one JSON snapshot per session
- one JSONL event log per session

### 2. Default storage location

Resolution order:

1. `CHATGPTREST_AGENT_SESSION_DIR`
2. sibling of `CHATGPTREST_DB_PATH`, under `agent_sessions/`
3. pytest-only temp directory
4. `/tmp/chatgptrest-agent-sessions`

That keeps runtime persistence durable while preserving isolated tests.

### 3. Replaced in-memory route-local stores

Inside `routes_agent_v3.py`, the route-local:

- `_session_store`
- `_session_events`

were replaced by `AgentSessionStore`.

The route-local closure helpers still expose the same semantics:

- `_session_copy(...)`
- `_upsert_session(...)`
- `_session_events_after(...)`
- `_append_session_event(...)`

So the public facade logic stayed stable while session durability improved.

### 4. Health surface

`/v3/agent/health` now reports `active_sessions` from the persisted store rather
than `len()` of an in-memory dict.

## Tests

Validated with:

```bash
./.venv/bin/pytest -q tests/test_routes_agent_v3.py
./.venv/bin/pytest -q tests/test_agent_v3_routes.py
./.venv/bin/pytest -q tests/test_bi14_fault_handling.py
./.venv/bin/pytest -q tests/test_agent_mcp.py
```

New regression coverage:

- `test_agent_session_survives_router_recreation_when_store_dir_is_persisted`

This verifies a session created under one router instance can still be queried
after recreating the router, which models API restart behavior.

## Outcome

Public agent facade sessions are now durable across API restarts, while the
existing public route contract remains unchanged.
