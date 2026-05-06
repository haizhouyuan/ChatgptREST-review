# 2026-04-04 W2 Planning Task Read Semantics Explicitization Execution Review v1

## This batch

This batch advances `W2-S2` by freezing read semantics instead of leaving them implicit:

1. REST planning task reads now expose whether they are `stateful_runtime_refresh` or `snapshot_only`
2. REST callers can explicitly disable refresh with `refresh=false`
3. checkpoint query CLIs now declare themselves as `snapshot_only`

## Actual code changes

1. [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py)
   - added `read_semantics` to:
     - `GET /v3/agent/planning/task/{task_id}`
     - `GET /v3/agent/planning/tasks`
   - added `refresh: bool = True`
   - `refresh=false` now skips read-time visibility refresh/writeback
2. [planning_task_checkpoint_get.py](/vol1/1000/projects/ChatgptREST/scripts/planning_task_checkpoint_get.py)
   - now returns `read_semantics = snapshot_only`
3. [planning_task_checkpoint_list.py](/vol1/1000/projects/ChatgptREST/scripts/planning_task_checkpoint_list.py)
   - now returns `read_semantics = snapshot_only`
4. tests:
   - [test_planning_task_checkpoint_query.py](/vol1/1000/projects/ChatgptREST/tests/test_planning_task_checkpoint_query.py)
   - [test_routes_agent_v3_planning_task_plane.py](/vol1/1000/projects/ChatgptREST/tests/test_routes_agent_v3_planning_task_plane.py)
   - [test_agent_v3_routes.py](/vol1/1000/projects/ChatgptREST/tests/test_agent_v3_routes.py)

## Why this matters

Before this batch, the system still had a medium design debt:

1. REST `GET/list` was a guarded stateful read
2. CLI `get/list` was a local snapshot read
3. but neither surface declared that difference clearly enough

That meant operators had to remember hidden semantics, and `W2-S2` was still mostly oral tradition.

After this batch:

1. the REST read side still keeps the phase-1 guarded refresh behavior by default
2. the caller can now opt out explicitly with `refresh=false`
3. CLI reads stop pretending to be equivalent and declare themselves as snapshot-only

## Validation

Passed:

1. `python3 -m py_compile chatgptrest/api/routes_agent_v3.py scripts/planning_task_checkpoint_get.py scripts/planning_task_checkpoint_list.py tests/test_planning_task_checkpoint_query.py tests/test_routes_agent_v3_planning_task_plane.py`
2. `./.venv/bin/pytest -q tests/test_planning_task_checkpoint_query.py tests/test_routes_agent_v3_planning_task_plane.py tests/test_agent_v3_routes.py`

## Current boundary after this batch

What is now true:

1. REST and CLI read surfaces now advertise their read mode
2. REST read-time refresh is now a visible contract, not only a hidden implementation detail
3. snapshot-only reads are available without forking another endpoint

What is still not done:

1. checkpoint schema still needs `W2-S3` handoff artifact elevation
2. REST default remains stateful refresh; that phase-1 design debt is now explicit, not removed
3. task/session/checkpoint truth still needs richer cross-end artifact shaping
