# Phase 10 Controller Route Parity Validation Completion Walkthrough v1

## What Changed

Added a new validation layer below Phase 9.

Phase 9 froze the public `/v3/agent/turn` route seam.
Phase 10 freezes the controller planning layer itself.

The validator now:

- builds canonical `task_intake`
- resolves/applies `scenario_pack`
- builds strategist output
- invokes live controller planning methods
- compares strategist route vs controller route

## Key Decisions

1. Did not expand to `ControllerEngine.ask()` full replay.
   That would mix route planning with downstream job creation and delivery,
   which is a separate layer.

2. Used a compatibility runtime shim.
   The first pass failed because advisor graph service lookup expects attribute
   access while controller logic expects `dict.get(...)`. The final validator
   uses a small shim that supports both.

3. Used grounded `research_report` input for controller coverage.
   This phase needed at least one report-grade research sample that can be
   meaningfully routed at the controller layer, so the dataset includes a
   grounded report request instead of the low-context clarify-first version
   used in Phase 9.

## Evidence

Generated artifacts:

- [report_v1.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/phase10_controller_route_parity_validation_20260322/report_v1.json)
- [report_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/phase10_controller_route_parity_validation_20260322/report_v1.md)

Final runner result:

- `items=5`
- `passed=5`
- `failed=0`

## Commit Trail

- `5c60be7` `feat: add phase10 controller route parity validation`
- current docs commit records the phase completion and artifacts

