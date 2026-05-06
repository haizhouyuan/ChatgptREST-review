# 2026-03-23 Heavy Execution Explicit-Only Closure v1

## Summary

This closeout finishes the remaining runtime gap from the earlier heavy-execution decision gate:

- heavy execution remains `NO-GO`
- heavy execution remains a `gated experimental lane`
- controller no longer keeps the residual implicit fallback
  - `route in {funnel, build_feature} -> team`

The live runtime state is now:

- explicit operator/admin surface still exists
- explicit topology/team intent still works
- implicit controller fallback is removed

## What changed

Code:

- `chatgptrest/controller/engine.py`
  - `_resolve_execution_kind()` no longer upgrades plain `funnel/build_feature` routes into `team`
  - `_build_objective_plan()` no longer labels plain `funnel/build_feature` routes as `team_delivery`
  - shared helper logic now treats team execution as explicit-only:
    - `scenario_pack.execution_preference == team`
    - `stable_context.team`
    - `stable_context.topology_id`
    - `executor_lane == "team"`

Validation:

- `tests/test_controller_engine_planning_pack.py`
- `tests/test_controller_route_parity_validation.py`
- `tests/test_branch_coverage_validation.py`
- `chatgptrest/eval/branch_coverage_validation.py`
- `eval_datasets/phase10_controller_route_parity_samples_v1.json`
- `eval_datasets/phase11_branch_coverage_samples_v1.json`

## Verified outcome

1. `workforce_planning` still stays on `route=funnel`, but controller execution remains `job`.
2. Plain `funnel` route with no explicit team intent now resolves to:
   - `execution_kind=job`
   - `objective_kind=answer`
3. Explicit topology request still resolves to `team`.
4. Phase 10 route parity and Phase 11 branch coverage both stay green after the closure:
   - `phase10_controller_route_parity_validation` -> `5/5`
   - `phase11_branch_coverage_validation` -> `4/4`

## Evidence

- [phase10 report_v2.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/phase10_controller_route_parity_validation_20260322/report_v2.json)
- [phase11 report_v2.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/phase11_branch_coverage_validation_20260322/report_v2.json)

## Final status

Heavy execution is now accurately described as:

- `gated experimental lane`
- `explicit-only`
- `not approved as a system center`

This closes the residual runtime mismatch that remained after the earlier decision-gate documentation work.
