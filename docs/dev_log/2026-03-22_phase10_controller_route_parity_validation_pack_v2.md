# Phase 10 Controller Route Parity Validation Pack v2

## Goal

Validate that the live controller planning layer remains aligned with the
current shared canonical scenario-pack policy for covered `planning/research`
pack routes, without going through the public `/v3/agent/turn` response seam.

## Scope

This phase validates the live controller planning surface for covered canonical
`planning/research` contexts by executing:

- [`ControllerEngine._plan_async_route()`](/vol1/1000/projects/ChatgptREST/chatgptrest/controller/engine.py#L1694)
- [`ControllerEngine._resolve_execution_kind()`](/vol1/1000/projects/ChatgptREST/chatgptrest/controller/engine.py#L827)
- [`ControllerEngine._build_objective_plan()`](/vol1/1000/projects/ChatgptREST/chatgptrest/controller/engine.py#L765)

Each sample compares:

- canonical scenario-pack profile
- strategist route hint
- controller selected route
- controller execution kind
- controller objective kind
- parity between controller and the shared scenario-pack-driven strategy

## What This Phase Is

- `controller parity validation for covered canonical pack routes`
- deeper than Phase 9 because it tests live controller planning logic directly
- focused on route planning, not downstream execution delivery

## What This Phase Is Not

- not `fully independent controller-route truth validation`
- not `ControllerEngine.ask()` full execution replay
- not job submission / artifact delivery validation
- not knowledge writeback or full-stack validation

## Dataset

Dataset file:

- [phase10_controller_route_parity_samples_v1.json](/vol1/1000/projects/ChatgptREST/eval_datasets/phase10_controller_route_parity_samples_v1.json)

Covered canonical samples:

1. lightweight `business_planning` -> `report/job`
2. `workforce_planning` -> `funnel/job`
3. `topic_research` -> `deep_research/job`
4. `comparative_research` -> `deep_research/job`
5. grounded `research_report` -> `report/job`

Explicitly not yet covered:

- `clarify_required=true` pre-controller cases
- `kb_used=true` direct-answer cases
- `no scenario_pack` fallback routes
- `team fallback` routes

## Implementation

Core validator:

- [controller_route_parity_validation.py](/vol1/1000/projects/ChatgptREST/chatgptrest/eval/controller_route_parity_validation.py)

Runner:

- [run_controller_route_parity_validation.py](/vol1/1000/projects/ChatgptREST/ops/run_controller_route_parity_validation.py)

Tests:

- [test_controller_route_parity_validation.py](/vol1/1000/projects/ChatgptREST/tests/test_controller_route_parity_validation.py)

The validator builds canonical context using the shared intake +
scenario-pack pipeline, then invokes the live controller planning methods with
a compatibility runtime shim that supports:

- `dict.get(...)` for controller state access
- attribute access for advisor graph service lookup

That means this phase checks controller parity against shared policy, not two
fully independent routing brains.

## Acceptance

Phase 10 passes only when:

- controller selected route matches the expected covered-pack route
- controller execution kind matches expected lane semantics
- controller objective kind matches the expected delivery shape
- strategist route hint and controller route remain in parity for every covered sample

