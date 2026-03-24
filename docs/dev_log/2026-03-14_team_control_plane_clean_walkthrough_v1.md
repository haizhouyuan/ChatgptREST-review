## Progress

1. Created clean worktree from current `origin/master` and recorded an execution plan before touching code.
2. Cherry-picked the feature-only commit from PR `#178`:
   - `2cb04b5` `feat: add team control plane runtime`
3. Ran impact/context analysis before editing the touched symbols:
   - `dispatch_team`: low-risk, direct callers concentrated in `tests/test_team_integration.py`
   - `_run_team_roles`: low-risk, upstream path funnels through `dispatch_team`
   - `_resolve_checkpoint`: low-risk, direct callers are approve/reject control-plane methods and advisor v3 routes
   - `resolve_team_spec`: critical-risk contract edge because it sits directly under `/v2/advisor/cc-dispatch-team`

## Implemented Fixes

### 1. Checkpoint Resolution

- Parent `team_run` no longer finalizes while checkpoints remain pending.
- Final status now resolves as:
  - `rejected` if any checkpoint was rejected
  - `completed` if all checkpoints are resolved and `final_ok=true`
  - `failed` if all checkpoints are resolved and `final_ok=false`

### 2. Topology Overlay

- Explicit `team` payloads can now be combined with `topology_id`.
- Roles remain explicit, while topology metadata/gates/execution mode are applied deterministically.
- Explicit non-topology metadata is preserved.

### 3. Concurrency Enforcement

- Parallel team fan-out now honors `max_concurrent` from topology metadata via a semaphore.
- `max_concurrent` is no longer dead config.

## Validation Completed So Far

```bash
python3 -m py_compile \
  chatgptrest/kernel/team_control_plane.py \
  chatgptrest/kernel/cc_native.py \
  tests/test_team_control_plane.py \
  tests/test_routes_advisor_v3_team_control.py \
  tests/test_team_integration.py

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
