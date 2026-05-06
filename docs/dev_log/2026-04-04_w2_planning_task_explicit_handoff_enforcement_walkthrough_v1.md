# 2026-04-04 W2 planning task explicit handoff enforcement walkthrough v1

## What I changed

I moved the first `W2` batch from “metadata only” to one real runtime contract:

1. if a caller explicitly passes `task_id`, the system now treats that as a strict handoff target;
2. if that target is missing or outside the caller's current visibility scope, the request fails closed;
3. if the caller tries to `continue` while also changing the planning task type, the request is rejected and must switch to `branch`.

## Why this batch was necessary

The planning task plane already had identity-gated `GET/list`, but the write-side handoff path still had two silent drifts:

1. explicit `task_id` could keep working even when query surfaces for the same caller would not expose that task;
2. explicit `task_id` miss could still slide into a different continue/new resolution path.

That made `task_id` weaker than it looked, and it prevented `W2-S1` from being called a real truth hardening step.

## Files changed

1. [meeting_task_store.py](/vol1/1000/projects/ChatgptREST/chatgptrest/planning/meeting_task_store.py)
2. [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py)
3. [test_meeting_task_store.py](/vol1/1000/projects/ChatgptREST/tests/test_meeting_task_store.py)
4. [test_routes_agent_v3_meeting_task_layer.py](/vol1/1000/projects/ChatgptREST/tests/test_routes_agent_v3_meeting_task_layer.py)
5. [test_routes_agent_v3_planning_task_plane.py](/vol1/1000/projects/ChatgptREST/tests/test_routes_agent_v3_planning_task_plane.py)
6. [AGENTS.md](/vol1/1000/projects/ChatgptREST/AGENTS.md)

## What changed in behavior

1. explicit `task_id` with a missing record now returns `planning_task_not_found`
2. explicit `task_id` across mismatched identity now also returns `planning_task_not_found`
3. explicit `continue` with a changed `planning_task_type` now returns `planning_task_contract_mismatch`
4. the suggested fix for the third case is explicit `planning_task_action=branch`

## Verification

Passed:

1. `python3 -m py_compile chatgptrest/planning/meeting_task_store.py chatgptrest/api/routes_agent_v3.py tests/test_meeting_task_store.py tests/test_routes_agent_v3_meeting_task_layer.py tests/test_routes_agent_v3_planning_task_plane.py`
2. `./.venv/bin/pytest -q tests/test_meeting_task_store.py tests/test_routes_agent_v3_meeting_task_layer.py tests/test_routes_agent_v3_planning_task_plane.py`

## Next

The next useful `W2` slice is `W2-S2`:

1. freeze REST `GET/list` read semantics explicitly instead of leaving them as implicit stateful reads;
2. make REST and CLI read surfaces advertise their read mode instead of relying on operator memory.
