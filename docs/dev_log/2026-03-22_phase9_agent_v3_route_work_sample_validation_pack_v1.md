# Phase 9 Agent V3 Route Work Sample Validation Pack v1

## Goal

Freeze a repeatable business-sample validation pack for the public `/v3/agent/turn`
route so route-level drift becomes visible before it shows up in OpenClaw or
downstream adapters.

## Scope

This phase validates the live `agent_v3` router behavior for representative
`planning/research` asks by replaying the real FastAPI route and inspecting:

- canonical `task_intake` after ingress normalization
- resolved `scenario_pack`
- strategist route/clarify decision
- final public response `status` and `provenance.route`
- whether the request stayed on the expected `controller` vs `clarify` branch

## What This Phase Is

- `public-route business-sample validation`
- `route-level replay` for `/v3/agent/turn`
- stronger than pure semantic snapshots because it goes through the live route

## What This Phase Is Not

- not `OpenClaw dynamic replay`
- not `full-stack business-sample validation`
- not `controller delivery / knowledge writeback / artifact payload` validation

## Dataset

Dataset file:

- [phase9_agent_v3_route_work_samples_v1.json](/vol1/1000/projects/ChatgptREST/eval_datasets/phase9_agent_v3_route_work_samples_v1.json)

Covered samples:

1. `interview_notes` clarify gate
2. `meeting_summary` clarify gate
3. lightweight `business_planning` -> `report`
4. `workforce_planning` -> `funnel`
5. `topic_research` -> `deep_research`
6. `comparative_research` -> `deep_research`
7. low-context `research_report` clarify gate

## Implementation

Core validator:

- [agent_v3_route_work_sample_validation.py](/vol1/1000/projects/ChatgptREST/chatgptrest/eval/agent_v3_route_work_sample_validation.py)

Runner:

- [run_agent_v3_route_work_sample_validation.py](/vol1/1000/projects/ChatgptREST/ops/run_agent_v3_route_work_sample_validation.py)

Tests:

- [test_agent_v3_route_work_sample_validation.py](/vol1/1000/projects/ChatgptREST/tests/test_agent_v3_route_work_sample_validation.py)

The validator uses:

- the live router from [`routes_agent_v3.py`](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py)
- a fake `ControllerEngine` that echoes the strategist route hint
- a wrapper around `build_strategy_plan(...)` to capture live route-context state
- guarded fake direct-job / consult branches so unexpected branch drift becomes visible

## Acceptance

Phase 9 passes only when:

- all dataset samples return HTTP `200`
- all expected `status` values match
- all expected public `route` values match
- all expected `scenario_pack` / `task_template` / `clarify` semantics match
- samples expected to stay on `controller` do not drift into direct-job or consult branches

