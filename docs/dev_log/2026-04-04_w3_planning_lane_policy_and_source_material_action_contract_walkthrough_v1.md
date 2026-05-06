# 2026-04-04 W3 planning lane policy and source material action contract walkthrough v1

## What I changed

I finished the two remaining `W3` items without reopening high-risk planner internals:

1. added a runtime-visible `lane_policy` payload to planning turns
2. froze the narrow compact implementation quick-ask path onto default `chatgpt`
3. upgraded attachment preflight from a descriptive posture into an explicit action contract
4. made the all-materials-blocked case stop before provider execution

## Why this batch was necessary

The previous state still had two operational gaps:

1. callers could see `scenario_pack`, but not whether provider choice was actually frozen or still implicit
2. preflight could say “these files need preprocessing”, but the public response still lacked a stable continue/preprocess/block contract

This meant the system could explain the situation, but not expose a crisp runtime policy.

## Files changed

1. [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py)
2. [meeting_task_store.py](/vol1/1000/projects/ChatgptREST/chatgptrest/planning/meeting_task_store.py)
3. [test_routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/tests/test_routes_agent_v3.py)
4. [test_routes_agent_v3_planning_task_plane.py](/vol1/1000/projects/ChatgptREST/tests/test_routes_agent_v3_planning_task_plane.py)
5. [test_meeting_task_store.py](/vol1/1000/projects/ChatgptREST/tests/test_meeting_task_store.py)
6. [AGENTS.md](/vol1/1000/projects/ChatgptREST/AGENTS.md)

## Behavior after the change

1. planning turns now expose `control_plane.lane_policy`
2. compact implementation quick-ask shows `provider_resolution=policy_default` and `default_provider=chatgpt`
3. unfrozen planning profiles explicitly show `manual_selection_required=true`
4. checkpoint and handoff payload now carry `source_material_action_contract / source_material_action_reason`
5. if every attached file still needs preprocessing, `/v3/agent/turn` returns `needs_input`, `await_workspace_patch`, and `control_plane.source_material_policy` before any provider job starts

## Verification

Passed:

1. `python3 -m py_compile chatgptrest/api/routes_agent_v3.py chatgptrest/planning/meeting_task_store.py tests/test_meeting_task_store.py tests/test_routes_agent_v3.py tests/test_routes_agent_v3_planning_task_plane.py`
2. `./.venv/bin/pytest -q tests/test_meeting_task_store.py tests/test_routes_agent_v3.py tests/test_agent_v3_routes.py tests/test_routes_agent_v3_meeting_task_layer.py tests/test_routes_agent_v3_planning_task_plane.py`

## Next

The `W2/W3` todo is now closed. The next unfinished work moves to `W4`:

1. wire stable work-memory ingress into the main planning flow
2. only then start broader memory governance and runtime-pack freshness work
