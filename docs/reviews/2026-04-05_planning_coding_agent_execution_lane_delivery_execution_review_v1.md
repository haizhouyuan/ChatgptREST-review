# 2026-04-05 Planning Coding-Agent Execution Lane Delivery Execution Review v1

## Scope

This batch moves the planning task plane from a boundary-only statement to a real multi-executor delivery path for the explicit `coding_agent` lane.

Implementation commit:

- `c6e5451c` `Add coding-agent planning execution lane`

This batch does **not** claim the full final execution layer is complete.
It only upgrades the proven contract from:

- `phase1_web_provider_subset`

to:

- `phase2_multi_executor_subset`

with the explicit planning execution lanes:

- `web`
- `coding_agent`

Future lanes still out of scope:

- `workspace`
- `specialized`

## Implemented

### 1. Planning can explicitly request a coding-agent lane

Files:

- `chatgptrest/api/routes_agent_v3.py`

What changed:

1. planning turn now derives `execution_request` from `task_intake.context`
2. explicit `requested_execution_lane=coding_agent` or explicit `requested_executor=*` no longer falls through to web-provider resolution
3. `control_plane.execution_layer` / `control_plane.planning_task.execution_layer` / `planning_query.snapshot|items[*].execution_layer` now project:
   - `execution_lane=coding_agent`
   - `executor_scope=phase2_multi_executor_subset`
   - `selected_executor / selected_executor_family`
   - `requested_executor / requested_effort`
   - `available_coding_executors`

### 2. ControllerEngine can actually execute the coding-agent lane

Files:

- `chatgptrest/controller/coding_agent_executor.py`
- `chatgptrest/controller/engine.py`

What changed:

1. added a real executor adapter layer for:
   - `codex`
   - `codex2`
   - `claudeminmax`
   - `claudegac`
2. `ControllerEngine` now resolves `execution_kind=coding_agent` when the planning turn explicitly asks for that lane
3. controller dispatch now runs the selected executor, stores a `coding_agent_result` artifact, and writes the final answer back through the existing controller delivery path

### 3. Codex structured-output contract was fixed against real runtime evidence

Files:

- `chatgptrest/controller/coding_agent_executor.py`
- `tests/test_coding_agent_executor.py`

What changed:

1. the first real Codex smoke failed because the schema omitted `additionalProperties: false`
2. the second real Codex smoke failed because the schema `required` list did not include every property
3. the contract was corrected to the strict schema Codex actually accepts:
   - `additionalProperties=false`
   - `required=[answer, summary]`
4. a regression test now freezes that contract

## Acceptance Result

Fresh acceptance evidence is frozen in:

- `docs/dev_log/artifacts/planning_coding_agent_lane_acceptance_20260405_v1/manifest.json`
- `docs/dev_log/artifacts/planning_coding_agent_lane_acceptance_20260405_v1/report_v1.md`
- `docs/dev_log/artifacts/planning_coding_agent_lane_acceptance_20260405_v1/turn_response_v1.json`
- `docs/dev_log/artifacts/planning_coding_agent_lane_acceptance_20260405_v1/controller_snapshot_v1.json`
- `docs/dev_log/artifacts/planning_coding_agent_lane_acceptance_20260405_v1/session_snapshot_v1.json`
- `docs/dev_log/artifacts/planning_coding_agent_lane_acceptance_20260405_v1/task_snapshot_v1.json`
- `docs/dev_log/artifacts/planning_coding_agent_lane_acceptance_20260405_v1/available_executors_v1.json`

Fresh acceptance statement:

1. explicit planning request with `requested_execution_lane=coding_agent`
2. explicit executor selection `requested_executor=codex`
3. controller terminal state `DELIVERED`
4. public session terminal state `completed`
5. planning task checkpoint/handoff updated with the coding-agent artifact path

Result:

- accepted

## Red-Team Note

`claudegac` review was attempted twice from the local wrapper during this batch, including a bounded `timeout 90s` run.
Both attempts produced no review output before timeout, so `claudegac` did **not** act as a blocking review gate for this batch.

Decision taken:

- do not block the implementation on a non-returning local wrapper
- rely on the actual acceptance evidence plus targeted tests for the go/no-go decision

## Validation

Python syntax:

- `./.venv/bin/python -m py_compile chatgptrest/controller/coding_agent_executor.py chatgptrest/controller/engine.py chatgptrest/api/routes_agent_v3.py tests/test_coding_agent_executor.py tests/test_controller_engine_planning_pack.py tests/test_routes_agent_v3.py tests/test_routes_agent_v3_planning_task_plane.py`

Targeted pytest:

- `./.venv/bin/pytest -q tests/test_coding_agent_executor.py tests/test_controller_engine_planning_pack.py tests/test_routes_agent_v3.py tests/test_routes_agent_v3_planning_task_plane.py`

Real acceptance run:

- artifact pack `docs/dev_log/artifacts/planning_coding_agent_lane_acceptance_20260405_v1/`

## Frozen Boundary

After this batch, the correct statement is:

> the planning task plane now proves a `phase2_multi_executor_subset` execution contract with explicit `web` and `coding_agent` lanes. `workspace` and `specialized` remain outside the current contract. Fresh end-to-end acceptance in this batch is frozen for explicit `codex`; the other coding-agent executors are included in the same contract and exposed as ready on this host, but were not individually smoke-validated in this batch.
