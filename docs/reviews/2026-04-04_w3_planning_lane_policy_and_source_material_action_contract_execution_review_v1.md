# 2026-04-04 W3 planning lane policy and source material action contract execution review v1

## This batch

This batch lands both remaining `W3` items:

1. `W3-S1`: planning lane policy is now runtime-visible
2. `W3-S2`: attachment preflight now projects an explicit action contract instead of only advisory posture

## Actual code changes

1. [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py)
   - added `control_plane.lane_policy`
   - provider selection now records whether it came from:
     - explicit request
     - policy default
     - runtime default still unfrozen
   - froze one narrow policy default:
     - `planning`
     - `profile=implementation_plan`
     - `route_hint=quick_ask`
     - `planning_mode=compact_next_steps`
     - default provider=`chatgpt`
   - added `control_plane.source_material_policy`
   - when all attached materials are `preflight_required`, the turn now short-circuits before `controller.ask` and returns `needs_input + await_workspace_patch`
2. [meeting_task_store.py](/vol1/1000/projects/ChatgptREST/chatgptrest/planning/meeting_task_store.py)
   - checkpoint now persists:
     - `source_material_action_contract`
     - `source_material_action_reason`
   - projected source-material posture now includes contract/reason in the public handoff shape
3. tests:
   - [test_routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/tests/test_routes_agent_v3.py)
   - [test_routes_agent_v3_planning_task_plane.py](/vol1/1000/projects/ChatgptREST/tests/test_routes_agent_v3_planning_task_plane.py)
   - [test_meeting_task_store.py](/vol1/1000/projects/ChatgptREST/tests/test_meeting_task_store.py)

## Why this matters

Before this batch:

1. planning provider resolution was still implicit for most callers, so the public surface could not say whether provider choice was frozen or still manual
2. attachment preflight could describe risk, but it did not expose a stable action contract
3. all-materials-blocked cases still depended on downstream behavior instead of failing closed at ingress

After this batch:

1. runtime payload explicitly says whether provider selection is `policy_default`, `manual_override`, or still `runtime_default_unfrozen`
2. canonical compact implementation quick-ask has a frozen default provider contract
3. source material policy explicitly distinguishes `continue`, `preprocess_first`, and `blocked`
4. the narrow `all materials require preprocessing` case now stops before provider execution and asks for the workspace patch directly

## Validation

Passed:

1. `python3 -m py_compile chatgptrest/api/routes_agent_v3.py chatgptrest/planning/meeting_task_store.py tests/test_meeting_task_store.py tests/test_routes_agent_v3.py tests/test_routes_agent_v3_planning_task_plane.py`
2. `./.venv/bin/pytest -q tests/test_meeting_task_store.py tests/test_routes_agent_v3.py tests/test_agent_v3_routes.py tests/test_routes_agent_v3_meeting_task_layer.py tests/test_routes_agent_v3_planning_task_plane.py`

## Current boundary after this batch

What is now true:

1. `W3-S1` is landed, but only one compact implementation planning path is provider-frozen by policy
2. `W3-S2` is landed as an action-contract layer, not only a descriptive posture layer
3. blocked preflight is now fail-closed for the narrow `all materials pending preprocessing` case

What is still not true:

1. lane policy is not yet a global provider policy engine for every planning profile
2. mixed material cases are still allowed to continue; they are labeled `preprocess_first`, not auto-blocked
3. `W4-W6` remain outside this batch
