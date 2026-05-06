# Phase 23 Walkthrough: Scoped Stack Readiness Gate v1

## Changes

- added aggregate gate module:
  - [scoped_stack_readiness_gate.py](/vol1/1000/projects/ChatgptREST/chatgptrest/eval/scoped_stack_readiness_gate.py)
- added runner:
  - [run_scoped_stack_readiness_gate.py](/vol1/1000/projects/ChatgptREST/ops/run_scoped_stack_readiness_gate.py)
- added tests:
  - [test_scoped_stack_readiness_gate.py](/vol1/1000/projects/ChatgptREST/tests/test_scoped_stack_readiness_gate.py)

## Validation

Commands run:

```bash
PYTHONPATH=. ./.venv/bin/python ops/run_scoped_stack_readiness_gate.py
```

Supporting validation for the new inputs:

```bash
./.venv/bin/pytest -q tests/test_api_provider_delivery_gate.py tests/test_auth_hardening_secret_source_gate.py tests/test_scoped_stack_readiness_gate.py tests/test_llm_connector.py -k 'api_provider_delivery_gate or auth_hardening_secret_source_gate or scoped_stack_readiness_gate or signal_emitter_includes_bound_trace_id or signal_emitter_omits_trace_id_without_binding'
PYTHONPATH=. ./.venv/bin/python ops/run_api_provider_delivery_gate.py
PYTHONPATH=. ./.venv/bin/python ops/run_auth_hardening_secret_source_gate.py
```

## Notes

- aggregate gate resolves latest available artifact versions instead of hard-pinning `report_v1`
- this avoids the earlier artifact-version drift problem seen in older aggregate gates
