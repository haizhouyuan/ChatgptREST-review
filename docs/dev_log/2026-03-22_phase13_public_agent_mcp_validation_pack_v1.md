# Phase 13 Public Agent MCP Validation Pack v1

## Goal

Freeze a transport-level validation pack for the public agent MCP surface so `chatgptrest-mcp.service` is no longer considered "usable" based on ad hoc manual probes.

## Scope

- Live `streamable-http` MCP endpoint at `http://127.0.0.1:18712/mcp`
- Public agent tool surface only:
  - `advisor_agent_turn`
  - `advisor_agent_cancel`
  - `advisor_agent_status`
- One canonical planning sample:
  - `请总结面试纪要`

## Non-goals

- OpenClaw dynamic replay
- Full-stack controller/runtime replay
- Long-running execution delivery
- Background watch completion correctness

## Checks

1. `initialize`
   - server name is `chatgptrest-agent-mcp`
   - protocol version is `2025-03-26`
2. `tools/list`
   - exact public tool set is exposed
3. `advisor_agent_turn`
   - planning sample returns `needs_followup`
   - route is `clarify`
   - next action is `await_user_clarification`
4. `advisor_agent_status`
   - same session id remains readable
   - route/status stay aligned with the clarify turn

## Implementation

- Validation module:
  - [chatgptrest/eval/public_agent_mcp_validation.py](/vol1/1000/projects/ChatgptREST/chatgptrest/eval/public_agent_mcp_validation.py)
- Runner:
  - [ops/run_public_agent_mcp_validation.py](/vol1/1000/projects/ChatgptREST/ops/run_public_agent_mcp_validation.py)
- Tests:
  - [tests/test_public_agent_mcp_validation.py](/vol1/1000/projects/ChatgptREST/tests/test_public_agent_mcp_validation.py)

## Acceptance

- Validation runner exits `0`
- Report shows `4/4` checks passed
- Planning sample reaches clarify through live MCP transport after API/MCP restart to current `HEAD`
