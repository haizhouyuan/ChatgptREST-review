# Phase 13 Public Agent MCP Validation Completion v1

## Result

`Phase 13` passed. Public agent MCP is now backed by a repeatable transport-level validation pack rather than one-off curl probes.

## What Was Verified

- Live `initialize` on `http://127.0.0.1:18712/mcp`
- Exact public tool surface:
  - `advisor_agent_turn`
  - `advisor_agent_cancel`
  - `advisor_agent_status`
- Live `advisor_agent_turn` for `请总结面试纪要`
  - returned `status=needs_followup`
  - returned `route=clarify`
  - returned `next_action.type=await_user_clarification`
- Live `advisor_agent_status`
  - returned the same `session_id`
  - preserved `status=needs_followup`
  - preserved `route=clarify`

## Important Finding

The earlier "public MCP looks wrong" symptom was not a persistent implementation bug. After restarting:

- `chatgptrest-api.service`
- `chatgptrest-mcp.service`

the live MCP path matched current `HEAD` behavior and clarified the planning sample as expected.

Inference: the earlier mismatch was caused by stale runtime processes, not by a surviving Phase 3 regression in the current codebase.

## Artifacts

- Validation report JSON:
  - [report_v1.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/phase13_public_agent_mcp_validation_20260322/report_v1.json)
- Validation report Markdown:
  - [report_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/phase13_public_agent_mcp_validation_20260322/report_v1.md)

## Boundaries

This phase proves:

- public MCP transport usability
- public tool surface stability
- public planning clarify continuity

This phase does not prove:

- OpenClaw dynamic replay
- full-stack execution completion
- long-running deferred watch lifecycle
