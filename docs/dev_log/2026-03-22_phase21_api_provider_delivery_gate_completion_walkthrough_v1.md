# Phase 21 Walkthrough: API Provider Delivery Gate v1

## Changes

- added live gate module:
  - [api_provider_delivery_gate.py](/vol1/1000/projects/ChatgptREST/chatgptrest/eval/api_provider_delivery_gate.py)
- added runner:
  - [run_api_provider_delivery_gate.py](/vol1/1000/projects/ChatgptREST/ops/run_api_provider_delivery_gate.py)
- added tests:
  - [test_api_provider_delivery_gate.py](/vol1/1000/projects/ChatgptREST/tests/test_api_provider_delivery_gate.py)
- kept previously added low-intrusion trace propagation in:
  - [llm_connector.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/llm_connector.py)
  - [graph.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/graph.py)

## Validation

Commands run:

```bash
./.venv/bin/pytest -q tests/test_api_provider_delivery_gate.py tests/test_auth_hardening_secret_source_gate.py tests/test_scoped_stack_readiness_gate.py tests/test_llm_connector.py -k 'api_provider_delivery_gate or auth_hardening_secret_source_gate or scoped_stack_readiness_gate or signal_emitter_includes_bound_trace_id or signal_emitter_omits_trace_id_without_binding'
python3 -m py_compile chatgptrest/eval/api_provider_delivery_gate.py chatgptrest/eval/auth_hardening_secret_source_gate.py chatgptrest/eval/scoped_stack_readiness_gate.py ops/run_api_provider_delivery_gate.py ops/run_auth_hardening_secret_source_gate.py ops/run_scoped_stack_readiness_gate.py tests/test_api_provider_delivery_gate.py tests/test_auth_hardening_secret_source_gate.py tests/test_scoped_stack_readiness_gate.py chatgptrest/kernel/llm_connector.py chatgptrest/advisor/graph.py tests/test_llm_connector.py
PYTHONPATH=. ./.venv/bin/python ops/run_api_provider_delivery_gate.py
```

## Notes

- initial manual probing showed `deep_research` delivery without same-trace `llm_connector` evidence
- this phase intentionally narrowed scope to a path that is actually provable today
- that is why the phase name is `API provider delivery gate`, not `external-provider delivery gate`
