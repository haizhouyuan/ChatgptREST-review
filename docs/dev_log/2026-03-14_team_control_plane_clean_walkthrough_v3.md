## Final Integration Summary

This clean branch started from current `origin/master`, cherry-picked the team-runtime feature commit from PR `#178`, and then completed the missing semantics needed to make the feature mergeable.

### Runtime / Contract Fixes

1. `chatgptrest/kernel/team_control_plane.py`
   - fixed checkpoint resolution so a `team_run` only finalizes once **all** checkpoints are resolved
   - made rejected checkpoints force a rejected/failure-style terminal outcome
   - added explicit overlay semantics for `topology_id` on top of caller-supplied `team`

2. `chatgptrest/kernel/cc_native.py`
   - enforced topology `max_concurrent` for parallel team fan-out via semaphore

3. `tests/*`
   - added regression coverage for multi-checkpoint approval, rejection, topology overlay, and parallel concurrency enforcement
   - hardened the team-control route test helper so full-suite order cannot leak a one-request rate limit into the control-plane route tests

## Validation

Targeted and broader feature matrices:

```bash
python3 -m py_compile \
  chatgptrest/kernel/team_control_plane.py \
  chatgptrest/kernel/cc_native.py \
  tests/test_team_control_plane.py \
  tests/test_routes_advisor_v3_team_control.py \
  tests/test_team_integration.py \
  tests/test_routes_advisor_v3_team_control.py

/vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q \
  tests/test_team_types.py \
  tests/test_team_control_plane.py \
  tests/test_team_integration.py \
  tests/test_routes_advisor_v3_team_control.py \
  tests/test_routes_advisor_v3_security.py

/vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q \
  tests/test_team_scorecard.py \
  tests/test_team_policy.py \
  tests/test_team_events.py \
  tests/test_advisor_runtime.py \
  tests/test_cc_executor_eventbus_smoke.py \
  tests/test_cc_executor.py
```

Follow-up validation after the order-dependent `429` diagnosis:

```bash
python3 -m py_compile tests/test_routes_advisor_v3_team_control.py

/vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q \
  tests/test_routes_advisor_v3_team_control.py \
  tests/test_routes_advisor_v3_security.py \
  tests/test_cognitive_api.py
```

Final full-repo validation:

```bash
/vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q
```

Result: full suite green.

## Scope Check

- feature scope relative to `origin/master` remains the clean team-control-plane slice:
  - `chatgptrest/advisor/runtime.py`
  - `chatgptrest/api/routes_advisor_v3.py`
  - `chatgptrest/kernel/cc_executor.py`
  - `chatgptrest/kernel/cc_native.py`
  - `chatgptrest/kernel/team_catalog.py`
  - `chatgptrest/kernel/team_control_plane.py`
  - `chatgptrest/kernel/team_types.py`
  - `config/codex_subagents.yaml`
  - `config/team_gates.yaml`
  - `config/team_topologies.yaml`
  - the associated tests and versioned docs

No unrelated product code was carried over from the original PR.
