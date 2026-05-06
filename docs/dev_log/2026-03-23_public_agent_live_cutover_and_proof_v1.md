# Public Agent Live Cutover And Proof v1

## Summary

This package closes the gap between the already-landed `public-agent-contract-first-upgrade`
code and the live public surface.

The key finding is simple:

- the contract-first fields were already implemented in code
- the live API/MCP processes were still running pre-upgrade code
- after refreshing `chatgptrest-api.service` and `chatgptrest-mcp.service`, the live public surface now projects the expected fields

## What Was Proved

The accepted live proof is captured by:

- raw `/v3/agent/turn`
- public MCP `advisor_agent_turn`
- repo wrapper `skills-src/chatgptrest-call/scripts/chatgptrest_call.py`
- same-session `contract_patch` with deferred continuation
- session projection after patch

Accepted artifact:

- [report_v1.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/public_agent_live_cutover_validation_20260323/report_v1.json)
- [report_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/public_agent_live_cutover_validation_20260323/report_v1.md)

Validation result:

- `7/7` checks passed

## Runtime Refresh Evidence

The stale-runtime hypothesis was confirmed by timestamps:

- `chatgptrest-api.service` had been running since `2026-03-23 00:20:20 CST`
- `chatgptrest-mcp.service` had been running since `2026-03-22 18:02:59 CST`
- the public-agent contract-first commits landed later on `2026-03-23`

The services were refreshed and are now running from:

- `chatgptrest-api.service` start time: `2026-03-23 13:38:11 CST`
- `chatgptrest-mcp.service` start time: `2026-03-23 13:38:11 CST`

## Live Surface Outcome

The live clarify response now visibly includes:

- `task_intake`
- `control_plane`
- `clarify_diagnostics`
- `next_action.clarify_diagnostics`

The same-session continuation proof now shows:

1. first turn blocks with `status=needs_followup` and `route=clarify`
2. second turn reuses the same `session_id` with `contract_patch`
3. the deferred response enters execution (`status=running`, `next_action.type=check_status`)
4. the refreshed session projection shows patched `task_intake`, `contract_source=client`, and `contract_completeness=1.0`

## Scope Boundary

This package proves:

- live public contract-first cutover
- raw API field projection
- public MCP field projection
- wrapper field projection
- same-session patch semantics on the live surface

This package does not prove:

- external provider completion quality
- full-stack deployment proof
- OpenClaw dynamic replay
- heavy execution lane approval
