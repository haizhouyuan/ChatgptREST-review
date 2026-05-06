## Summary

This validation pack verifies the public-agent contract-first upgrade at the route/control-plane level.

It covers:

1. canonical `task_intake` northbound submission
2. same-session `contract_patch`
3. `thinking_heavy` execution-profile routing
4. machine-readable clarify diagnostics
5. message-contract parser fallback
6. northbound observability projection through session state

## Scope

This pack validates the public control plane using an in-process route harness with a fake controller. It is intended to prove contract/control-plane behavior without depending on external provider runtime stability.

It complements, but does not replace, live transport validation:

- public MCP transport
- auth / trace gate
- scoped release / launch candidate gates

## Cases

### 1. canonical_task_intake_northbound

Verifies that structured `task_intake` fields reach the public route and remain visible in:

- response `task_intake`
- response `control_plane`
- session projection

including:

- `acceptance`
- `evidence_required`
- `requested_execution_profile`
- `effective_execution_profile`

### 2. clarify_machine_readable_diagnostics

Verifies that clarify responses now include machine-readable diagnostics:

- `missing_fields`
- `contract_completeness`
- `clarify_gate_reason`
- `clarify_reason_detail`
- `recommended_contract_patch`
- `recommended_resubmit_payload`

### 3. same_session_contract_patch_resume

Verifies that `contract_patch` can be applied under the same `session_id`, and that execution continues instead of opening a new task.

### 4. session_projection_retains_control_plane

Verifies that status reads preserve:

- `task_intake`
- `control_plane`
- patched contract fields

after the clarify -> patch -> execute sequence.

### 5. message_contract_parser_fallback

Verifies that labeled message-only input can still produce a structured contract path and that the response records:

- `parser_fallback_used=true`
- `contract_source=message_parser`

### 6. northbound_observability_projection

Verifies that northbound observability fields survive to session reads, especially:

- execution profile
- acceptance profile
- evidence level

## Artifacts

- JSON report: [report_v1.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/public_agent_contract_first_validation_20260323/report_v1.json)
- Markdown report: [report_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/public_agent_contract_first_validation_20260323/report_v1.md)

## Verification

Passed:

```bash
./.venv/bin/pytest -q \
  tests/test_routes_agent_v3.py \
  tests/test_skill_chatgptrest_call.py \
  tests/test_check_public_mcp_client_configs.py \
  tests/test_public_agent_contract_first_validation.py

python3 -m py_compile \
  chatgptrest/api/routes_agent_v3.py \
  chatgptrest/eval/public_agent_contract_first_validation.py \
  skills-src/chatgptrest-call/scripts/chatgptrest_call.py \
  ops/check_public_mcp_client_configs.py \
  ops/run_public_agent_contract_first_validation.py

PYTHONPATH=. ./.venv/bin/python ops/run_public_agent_contract_first_validation.py
```
