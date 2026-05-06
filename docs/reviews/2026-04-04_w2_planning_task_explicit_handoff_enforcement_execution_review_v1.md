# 2026-04-04 W2 Planning Task Explicit Handoff Enforcement Execution Review v1

## This batch

This batch advances `W2-S1` by turning one previously soft handoff rule into runtime enforcement:

1. explicit `task_id` continue/branch now uses the same visibility boundary as planning task `GET/list`;
2. explicit `task_id` can no longer silently fall back to another identity's task or to a fresh/new path;
3. explicit `continue` with a changed planning task type now fails closed and requires `branch`.

## Actual code changes

1. [meeting_task_store.py](/vol1/1000/projects/ChatgptREST/chatgptrest/planning/meeting_task_store.py)
   - added `PlanningTaskResolutionError`
   - explicit `task_id` now fails closed when:
     - the record is missing
     - the current identity cannot see the task
     - `continue` is attempted with a changed `task_type`
2. [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py)
   - maps explicit handoff failures to truthful public errors:
     - `404 planning_task_not_found`
     - `409 planning_task_contract_mismatch`
3. tests:
   - [test_meeting_task_store.py](/vol1/1000/projects/ChatgptREST/tests/test_meeting_task_store.py)
   - [test_routes_agent_v3_meeting_task_layer.py](/vol1/1000/projects/ChatgptREST/tests/test_routes_agent_v3_meeting_task_layer.py)
   - [test_routes_agent_v3_planning_task_plane.py](/vol1/1000/projects/ChatgptREST/tests/test_routes_agent_v3_planning_task_plane.py)

## Why this matters

Before this change, the planning truth layer had a real boundary mismatch:

1. `GET/list` already failed closed on identity;
2. but `turn + explicit task_id` could still continue the record without the same visibility check;
3. and an explicit `task_id` miss could still drift into a different continue/new path.

That meant `task_id` was not yet a trustworthy handoff anchor.

After this change:

1. explicit handoff no longer bypasses task visibility;
2. explicit handoff no longer hides missing-task mistakes behind fallback behavior;
3. `continue` vs `branch` is now materially enforced, not just described in metadata.

## Validation

Passed:

1. `python3 -m py_compile chatgptrest/planning/meeting_task_store.py chatgptrest/api/routes_agent_v3.py tests/test_meeting_task_store.py tests/test_routes_agent_v3_meeting_task_layer.py tests/test_routes_agent_v3_planning_task_plane.py`
2. `./.venv/bin/pytest -q tests/test_meeting_task_store.py tests/test_routes_agent_v3_meeting_task_layer.py tests/test_routes_agent_v3_planning_task_plane.py`

## Current boundary after this batch

What is now true:

1. explicit `task_id` handoff is no longer a visibility bypass;
2. explicit `continue` with changed output intent must become `branch`;
3. the public error surface is now truthful enough for operator/debug use.

What is still not done:

1. `GET/list` read semantics are still stateful on the REST path and snapshot-only on the CLI path;
2. checkpoint schema is still not the full final handoff artifact;
3. `task_contract` still is not a full task engine.
