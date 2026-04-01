## Background

`tests/test_advisor_v3_end_to_end.py` started failing after the security suite tightened
`OPENMIND_RATE_LIMIT=1`. The end-to-end helper built a fresh router but inherited the
mutated process environment, so the second request in the round-trip (`/trace/{id}` or
subsequent stats lookup) could be rate-limited even though the test was not asserting
rate-limit behavior.

## Change

- reset `OPENMIND_RATE_LIMIT` inside the v3 end-to-end `_make_client()` helper before
  creating the router

## Why

- keep the end-to-end suite focused on trace/EvoMap round-trip behavior
- leave the rate-limit contract owned by `tests/test_routes_advisor_v3_security.py`
- avoid cross-test env leakage producing false negatives

## Validation

- `./.venv/bin/pytest -q tests/test_advisor_v3_end_to_end.py tests/test_routes_advisor_v3_security.py`
- `./.venv/bin/python -m py_compile tests/test_advisor_v3_end_to_end.py`
