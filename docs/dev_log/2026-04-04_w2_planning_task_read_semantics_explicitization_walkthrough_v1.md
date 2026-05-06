# 2026-04-04 W2 planning task read semantics explicitization walkthrough v1

## What I changed

I turned the planning read path from “you have to know the hidden behavior” into an explicit contract:

1. REST `planning/task` and `planning/tasks` now return `read_semantics`
2. REST supports `refresh=false` for snapshot-only reads
3. local checkpoint query CLIs now also return `read_semantics`, explicitly marked as snapshot-only

## Why this batch was necessary

The previous state was still awkward:

1. REST `GET/list` did a guarded refresh and could write back on divergence
2. CLI `get/list` was a plain local read
3. but neither surface said so clearly enough in the payload

This was exactly the kind of read/write ambiguity `W2-S2` was supposed to remove.

## Files changed

1. [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py)
2. [planning_task_checkpoint_get.py](/vol1/1000/projects/ChatgptREST/scripts/planning_task_checkpoint_get.py)
3. [planning_task_checkpoint_list.py](/vol1/1000/projects/ChatgptREST/scripts/planning_task_checkpoint_list.py)
4. [test_planning_task_checkpoint_query.py](/vol1/1000/projects/ChatgptREST/tests/test_planning_task_checkpoint_query.py)
5. [test_routes_agent_v3_planning_task_plane.py](/vol1/1000/projects/ChatgptREST/tests/test_routes_agent_v3_planning_task_plane.py)
6. [AGENTS.md](/vol1/1000/projects/ChatgptREST/AGENTS.md)

## Behavior after the change

1. REST default:
   - `read_mode = stateful_runtime_refresh`
   - guarded writeback remains possible
2. REST opt-out:
   - `refresh=false`
   - `read_mode = snapshot_only`
3. CLI:
   - `read_mode = snapshot_only`
   - no hidden refresh/writeback implication

## Verification

Passed:

1. `python3 -m py_compile chatgptrest/api/routes_agent_v3.py scripts/planning_task_checkpoint_get.py scripts/planning_task_checkpoint_list.py tests/test_planning_task_checkpoint_query.py tests/test_routes_agent_v3_planning_task_plane.py`
2. `./.venv/bin/pytest -q tests/test_planning_task_checkpoint_query.py tests/test_routes_agent_v3_planning_task_plane.py tests/test_agent_v3_routes.py`

## Next

`W2-S1` and `W2-S2` now both have real code. The next meaningful step is `W2-S3`: upgrade checkpoint shape itself into a stronger handoff artifact instead of only tightening access and read semantics around the current shape.
