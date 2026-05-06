# 2026-04-05 Planning Coding-Agent Execution Lane Delivery Walkthrough v1

## What I Changed

I stopped treating the planning execution layer as “web-only truth” and added a real explicit `coding_agent` lane.

The implementation landed in:

- `chatgptrest/controller/coding_agent_executor.py`
- `chatgptrest/controller/engine.py`
- `chatgptrest/api/routes_agent_v3.py`

I also added targeted tests in:

- `tests/test_coding_agent_executor.py`
- `tests/test_controller_engine_planning_pack.py`
- `tests/test_routes_agent_v3.py`
- `tests/test_routes_agent_v3_planning_task_plane.py`

## Key Decisions

1. keep default planning behavior unchanged unless the caller explicitly asks for `requested_execution_lane=coding_agent` or a concrete `requested_executor`
2. model the coding-agent lane as a first-class planning execution lane instead of pretending team runtime already covers real `codex / claude` execution
3. expose the truth in northbound surfaces instead of leaving executor selection implicit

## What Broke During Real Smoke

The first real `codex` acceptance run failed before model execution because the structured-output schema was too loose:

- missing `additionalProperties=false`

The second real `codex` acceptance run failed because the schema was still not strict enough for Codex:

- `required` did not include every property

I fixed both issues in `chatgptrest/controller/coding_agent_executor.py`, added a regression test, and reran acceptance.

## What Passed

The final acceptance pack is:

- `docs/dev_log/artifacts/planning_coding_agent_lane_acceptance_20260405_v1/`

The frozen successful run is:

- `run_id=4d159c27bf4249f9b9a93189a9ce145d`
- `session_id=agent_sess_17b220649ecc4efc`
- `task_id=pln_0eaca2afdf88`

Frozen result:

1. explicit planning request entered `execution_lane=coding_agent`
2. selected executor was `codex`
3. controller terminal state became `DELIVERED`
4. public session terminal state became `completed`
5. planning task checkpoint/handoff carried the coding-agent artifact path

## Red-Team Attempt

I attempted to use local `claudegac` as a red-team reviewer twice.
The local wrapper never returned review text before timeout, including under `timeout 90s`.

I therefore treated it as a local wrapper/runtime availability problem, not as a blocker for the actual execution-lane delivery result.

## Why This Matters

Before this batch:

- planning execution truth could only honestly say `web-only`

After this batch:

- planning execution truth can honestly say:
  - `available_execution_lanes=[web, coding_agent]`
  - `available_coding_executors=[codex, codex2, claudeminmax, claudegac]`
  - explicit coding-agent planning requests no longer leak into web-provider routing

## Remaining Boundary

This is still not the full final execution layer.
The current proven boundary is:

- `web`
- `coding_agent`

Still out of scope:

- `workspace`
- `specialized`
