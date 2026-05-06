## Summary

The `public-agent-contract-first-upgrade` package is now complete.

Completed items:

1. `P0`: public MCP supports canonical `task_intake`
2. `P0`: public MCP supports `contract_patch` and same-session continuation
3. `P0`: clarify gate is explicitly execution-profile aware for `thinking_heavy`
4. `P1`: machine-readable clarify diagnostics are exposed
5. `P1`: message contract parser fallback exists
6. `P2`: `acceptance / evidence / observability` are northbound-visible through `task_intake` + `control_plane`
7. `P2`: validation pack and coding-agent governance cutover are in place

## What Was Finished In This Package

### Northbound contract exposure

Public MCP now supports:

- `task_intake`
- `contract_patch`

and the repo CLI / skill surfaces were aligned around these canonical objects.

### Same-session continuation

Clarify no longer forces a new task. Callers can patch the contract under the same `session_id` and continue execution.

### `thinking_heavy` policy

`thinking_heavy` is no longer only a route tweak. The clarify gate now treats it as a fast premium analysis lane when the core contract is present.

### Machine-readable clarify

Clarify responses now include enough machine-readable structure for coding agents to self-repair:

- missing fields
- reason code
- reason detail
- suggested contract patch
- suggested resubmit payload

### Parser fallback

Message-only callers can now recover labeled structure instead of collapsing everything into one raw objective.

### Northbound observability

Public responses and session projections now expose:

- requested/effective execution profile
- contract source
- contract completeness
- parser fallback used
- acceptance policy
- evidence policy

### Governance cutover

Coding-agent governance is now stricter:

- public MCP is the default northbound surface
- repo skill wrapper agent mode uses public MCP
- config checker verifies both Codex configs and wrapper default path
- policy docs and AGENTS/runbook wording were updated to reflect MCP-first governance

## Key Files

Core control-plane changes:

- [agent_mcp.py](/vol1/1000/projects/ChatgptREST/chatgptrest/mcp/agent_mcp.py)
- [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py)
- [task_intake.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/task_intake.py)
- [ask_contract.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/ask_contract.py)
- [ask_strategist.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/ask_strategist.py)
- [message_contract_parser.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/message_contract_parser.py)

Governance / wrapper cutover:

- [chatgptrest_call.py](/vol1/1000/projects/ChatgptREST/skills-src/chatgptrest-call/scripts/chatgptrest_call.py)
- [check_public_mcp_client_configs.py](/vol1/1000/projects/ChatgptREST/ops/check_public_mcp_client_configs.py)
- [2026-03-23_coding_agent_mcp_surface_policy_v2.md](/vol1/1000/projects/ChatgptREST/docs/2026-03-23_coding_agent_mcp_surface_policy_v2.md)

Validation:

- [public_agent_contract_first_validation.py](/vol1/1000/projects/ChatgptREST/chatgptrest/eval/public_agent_contract_first_validation.py)
- [report_v1.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/public_agent_contract_first_validation_20260323/report_v1.json)

## Completion State

This package upgrades the public surface from "message-first agent ask" toward a real contract-first northbound interface.

It also proves the repo skill wrapper now rides the same northbound surface: a live `chatgptrest_call.py --question '请总结面试纪要' --goal-hint planning` probe now returns a public-MCP `needs_followup + route=clarify` response instead of depending on direct `/v3/agent/*` REST.

It does **not** mean:

- full-stack deployment proof
- heavy execution lane approval
- arbitrary raw preset passthrough

It does mean the public agent surface is now substantially closer to the intended single northbound interface for Codex / Claude Code / Antigravity.
