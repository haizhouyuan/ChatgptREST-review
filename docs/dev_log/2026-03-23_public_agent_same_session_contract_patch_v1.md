# Public Agent Same-Session Contract Patch v1

## Summary

This slice adds formal same-session contract patch semantics to `/v3/agent/turn`.

Clients can now:

- reuse an existing `session_id`
- send `contract_patch`
- continue execution against the prior session contract/intake state

without rebuilding the entire request contract from scratch.

## What changed

Server-side session state now persists:

- `task_intake`
- `contract`
- `scenario_pack`
- `control_plane`
- `clarify_diagnostics`

Clarify responses now include machine-readable patch hints:

- `missing_fields`
- `contract_completeness`
- `clarify_gate_reason`
- `recommended_contract_patch`
- `recommended_resubmit_payload`

`/v3/agent/session/{id}` now returns these persisted control-plane objects too.

## Patch semantics

- `contract_patch` requires an existing session
- when present, the server merges:
  - stored session `task_intake`
  - explicit request `task_intake`
  - `contract_patch`
- stored `contract` is also reused as the base contract when patching
- if the prior objective was weak and the resubmitted message is richer, the new message can replace the stored objective

## Verification

```bash
./.venv/bin/pytest -q tests/test_agent_v3_routes.py tests/test_routes_agent_v3.py
python3 -m py_compile chatgptrest/api/routes_agent_v3.py tests/test_agent_v3_routes.py tests/test_routes_agent_v3.py
```
