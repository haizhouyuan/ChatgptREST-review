## Additional Validation Pass

After the first full-repo `pytest -q` run, the suite stopped at:

- `tests/test_routes_advisor_v3_team_control.py::test_cc_team_run_and_checkpoint_routes`

The failure was **not** a new team-runtime semantic regression. The route returned `429` on the second control-plane read because the test helper inherited a leaked process-wide `OPENMIND_RATE_LIMIT=1` from earlier suite state.

## Root Cause

- `make_v3_advisor_router()` snapshots `OPENMIND_RATE_LIMIT` when the router is created.
- `tests/test_routes_advisor_v3_team_control.py::_make_client()` set auth/control env vars, but did **not** set `OPENMIND_RATE_LIMIT`.
- Under full-suite ordering, another test had already left the process env at `OPENMIND_RATE_LIMIT=1`, so the team-control route test built a router with a one-request budget and tripped `429`.

This was a **test isolation** issue, not a production-path defect in team control plane semantics.

## Follow-up Fix

- Updated `tests/test_routes_advisor_v3_team_control.py::_make_client()` to set:

```python
monkeypatch.setenv("OPENMIND_RATE_LIMIT", "100")
```

This makes the helper self-contained and removes order dependence.

## Verification

Focused validation after the fix:

```bash
python3 -m py_compile tests/test_routes_advisor_v3_team_control.py

/vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q \
  tests/test_routes_advisor_v3_team_control.py \
  tests/test_routes_advisor_v3_security.py \
  tests/test_cognitive_api.py
```

GitNexus scope check was attempted through a fresh agent because the main session transport is stale. The effective result for the uncommitted fix was:

- touched symbol: `tests/test_routes_advisor_v3_team_control.py::_make_client`
- production runtime symbols: unchanged
- risk: low

The next step is one final full-repo `pytest -q` run on this clean branch.
