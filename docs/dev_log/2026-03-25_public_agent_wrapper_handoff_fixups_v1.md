# 2026-03-25 Public Agent Wrapper Handoff Fixups v1

## Context

Client-side live validation on `2026-03-25` exposed two wrapper-facing problems after the earlier public-agent boundary work:

1. Local preflight validation failures were still labeled as `still_running_possible=true`, which incorrectly pushed clients toward `advisor_agent_status` / `advisor_agent_wait` for requests that never left the wrapper.
2. The shared `chatgptrest_call.py` wrapper was still issuing bare streamable-HTTP `tools/call` requests and keeping long review-style turns on the initial `advisor_agent_turn` call, leaving clients with weak early observability and a transport path that diverged from the repo’s validated MCP handshake.

## What changed

### Wrapper transport + handoff

- `skills-src/chatgptrest-call/scripts/chatgptrest_call.py`
  - Added an MCP `initialize` handshake and best-effort `notifications/initialized` before `tools/call`.
  - Added negotiated MCP session headers (`mcp-session-id`, `mcp-protocol-version`) to subsequent tool calls.
  - For review/research/report/image style agent requests, or requests carrying attachments / `github_repo` / `enable_import_code`, the wrapper now:
    - requests `delivery_mode=deferred`
    - writes an early summary snapshot with the generated `session_id`
    - waits via `advisor_agent_wait` instead of holding a long opaque sync `advisor_agent_turn` open

### Failure classification

- Agent-mode errors now carry:
  - `submission_started`
  - `failure_stage` (`preflight`, `initialize_mcp`, `submit_turn`, `wait`)
- `still_running_possible=true` is now only emitted for post-submit transport timeout/disconnect cases.
- Local validation failures no longer instruct the client to recover a non-existent remote session.

## Verification

- `./.venv/bin/python -m py_compile skills-src/chatgptrest-call/scripts/chatgptrest_call.py`
- `./.venv/bin/pytest -q tests/test_skill_chatgptrest_call.py`
- `./.venv/bin/pytest -q tests/test_routes_agent_v3.py -k 'requested_gemini_code_review or gemini_import_code_deep_research_conflict'`

## Live runtime note

- Restarted:
  - `chatgptrest-api.service`
  - `chatgptrest-mcp.service`
- Post-restart, the public MCP validation confirmed the live service is again answering `initialize` and `tools/list` on fresh processes.
- The legacy `public_agent_mcp_validation` clarify baseline still reports an unrelated route drift (`planning_clarify_turn` resolved to `report/running` instead of `clarify/needs_followup`). That drift predates this wrapper fix and was not changed here.
