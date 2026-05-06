# Phase 22 Walkthrough: Auth Hardening Secret Source Gate v1

## Changes

- added gate module:
  - [auth_hardening_secret_source_gate.py](/vol1/1000/projects/ChatgptREST/chatgptrest/eval/auth_hardening_secret_source_gate.py)
- added runner:
  - [run_auth_hardening_secret_source_gate.py](/vol1/1000/projects/ChatgptREST/ops/run_auth_hardening_secret_source_gate.py)
- added tests:
  - [test_auth_hardening_secret_source_gate.py](/vol1/1000/projects/ChatgptREST/tests/test_auth_hardening_secret_source_gate.py)

## Validation

Commands run:

```bash
./.venv/bin/pytest -q tests/test_auth_hardening_secret_source_gate.py tests/test_scoped_stack_readiness_gate.py
python3 -m py_compile chatgptrest/eval/auth_hardening_secret_source_gate.py chatgptrest/eval/scoped_stack_readiness_gate.py
PYTHONPATH=. ./.venv/bin/python ops/run_auth_hardening_secret_source_gate.py
```

## Debugging Notes

- the first live red result was not a real secret leak
- root cause was gate logic:
  - it scanned every loaded config value, including non-secret allowlist strings
- the final gate only scans actual auth secret fields:
  - `OPENMIND_API_KEY`
  - `CHATGPTREST_API_TOKEN`
