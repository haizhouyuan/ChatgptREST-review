---
title: Execution Layer Governance Runtime Projection Walkthrough
status: completed
updated: 2026-04-17
owner: Codex
related:
  - docs/contracts/2026-04-17_execution_layer_governance_contract_v1.md
  - docs/ops/2026-04-17_public_surface_acceptance_split_v1.md
---

# 2026-04-17 Execution Layer Governance Runtime Projection Walkthrough v1

## What changed

This slice completed the first runtime implementation of execution-layer governance on canonical public MCP.

### Runtime

- added `chatgptrest/core/execution_governance.py`
- canonical `automation_ask` now accepts:
  - `requested_execution_lane`
  - `premium_allowed`
  - `task_object_contract`
- canonical preflight now fail-closes on:
  - unsupported automation lane
  - lane mismatch
  - premium disallowed but effective lane premium
- governance truth is persisted into stored job metadata (`client.execution_governance`)
- `/v1/jobs/{id}` and `/v1/jobs/{id}/result` now project:
  - requested/effective lane
  - requested/effective provider/preset
  - rewrite source/reason
  - runtime fallback fields
  - provider capability profile
  - premium authorization / justification
  - task object contract
- `_job_local_snapshot(...)` now projects the same governance truth for MCP background-wait / push consumers

### Acceptance / validation

- transport-only public MCP validation was rewritten as `probe` evidence, not premium happy-path evidence
- probe sample now uses:
  - object-framed prompt
  - `chatgpt + auto`
  - `requested_execution_lane=web_standard`
  - `premium_allowed=false`

## Why this matters

Before this slice, governance truth still had to be reconstructed from:

- `params_json`
- `client_json`
- artifacts
- executor fallback traces

After this slice, the core governance fields are readable directly from canonical receipt / job view / result view.

## Tests

Validated with:

- `tests/test_provider_registry.py`
- `tests/test_low_level_ask_guard.py`
- `tests/test_mcp_unified_ask_min_chars.py`
- `tests/test_public_agent_mcp_validation.py`
- `tests/test_agent_mcp.py`
- `tests/test_executor_pro_fallback.py`
- `tests/test_routes_agent_v3.py`
- `tests/test_mcp_server_entrypoints.py`
- `tests/test_agent_v3_routes.py`
- `tests/test_job_view_progress_fields.py`

