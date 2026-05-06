# Phase 15 Public Surface Launch Gate Pack v1

## Goal

Provide a single launch gate for the currently supported public ChatgptREST surface:

- core ask path
- public agent MCP
- strict Pro smoke blocking
- live health

## Inputs

- [phase12 core ask launch gate report](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/phase12_core_ask_launch_gate_20260322/report_v1.json)
- [phase13 public agent MCP validation report](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/phase13_public_agent_mcp_validation_20260322/report_v1.json)
- [phase14 strict Pro smoke block report](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/phase14_strict_pro_smoke_block_validation_20260322/report_v1.json)
- live `GET http://127.0.0.1:18711/healthz`
- live MCP `initialize` on `http://127.0.0.1:18712/mcp`

## Checks

1. `phase12_core_ask_launch_gate`
2. `phase13_public_agent_mcp_validation`
3. `phase14_strict_pro_smoke_block_validation`
4. `live_api_health`
5. `live_public_mcp_initialize`

## Implementation

- Validation module:
  - [chatgptrest/eval/public_surface_launch_gate.py](/vol1/1000/projects/ChatgptREST/chatgptrest/eval/public_surface_launch_gate.py)
- Runner:
  - [ops/run_public_surface_launch_gate.py](/vol1/1000/projects/ChatgptREST/ops/run_public_surface_launch_gate.py)
- Tests:
  - [tests/test_public_surface_launch_gate.py](/vol1/1000/projects/ChatgptREST/tests/test_public_surface_launch_gate.py)

## Acceptance

- runner exits `0`
- report shows `overall_passed=true`
- report shows `5/5` checks passed
