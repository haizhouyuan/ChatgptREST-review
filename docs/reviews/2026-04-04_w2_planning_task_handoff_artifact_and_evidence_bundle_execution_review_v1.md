# 2026-04-04 W2 planning task handoff artifact and evidence bundle execution review v1

## This batch

This batch lands `W2-S3` and the matching cross-surface evidence-bundle alignment:

1. planning checkpoint now persists a stronger handoff artifact instead of only mixed legacy fields
2. REST / CLI / session / OpenClaw summary layers now project the same handoff shape
3. deep-workbench writeback CLIs can now write the new handoff fields explicitly

## Actual code changes

1. [meeting_task_store.py](/vol1/1000/projects/ChatgptREST/chatgptrest/planning/meeting_task_store.py)
   - checkpoint now persists:
     - `stable_facts`
     - `pending_actions`
     - `last_completed_step`
     - `next_recommended_step`
     - `writeback_evidence`
   - added compatibility shaping so old records still project a usable handoff from:
     - `confirmed_scope`
     - `next_actions`
     - `artifact_refs`
     - `next_step`
   - public planning task payload now includes `handoff`
2. [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py)
   - session public payload now enriches stored planning task state with the same `handoff`
   - `GET /v3/agent/session/{session_id}` now also exposes top-level `planning_task`
3. CLI writeback/query surfaces:
   - [planning_task_checkpoint_get.py](/vol1/1000/projects/ChatgptREST/scripts/planning_task_checkpoint_get.py)
   - [planning_task_checkpoint_list.py](/vol1/1000/projects/ChatgptREST/scripts/planning_task_checkpoint_list.py)
   - [planning_task_checkpoint_writeback.py](/vol1/1000/projects/ChatgptREST/scripts/planning_task_checkpoint_writeback.py)
   - [planning_task_checkpoint_complete.py](/vol1/1000/projects/ChatgptREST/scripts/planning_task_checkpoint_complete.py)
4. OpenClaw plugin summary layer:
   - [index.ts](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-advisor/index.ts)
5. tests:
   - [test_meeting_task_store.py](/vol1/1000/projects/ChatgptREST/tests/test_meeting_task_store.py)
   - [test_planning_task_checkpoint_query.py](/vol1/1000/projects/ChatgptREST/tests/test_planning_task_checkpoint_query.py)
   - [test_planning_task_checkpoint_writeback.py](/vol1/1000/projects/ChatgptREST/tests/test_planning_task_checkpoint_writeback.py)
   - [test_planning_task_checkpoint_complete.py](/vol1/1000/projects/ChatgptREST/tests/test_planning_task_checkpoint_complete.py)
   - [test_routes_agent_v3_planning_task_plane.py](/vol1/1000/projects/ChatgptREST/tests/test_routes_agent_v3_planning_task_plane.py)
   - [test_openclaw_cognitive_plugins.py](/vol1/1000/projects/ChatgptREST/tests/test_openclaw_cognitive_plugins.py)

## Why this matters

Before this batch, the system still had a real handoff gap:

1. checkpoint carried useful facts, but the operator had to reconstruct the handoff mentally
2. CLI compact payload, REST planning payload, and session payload did not expose the same structure
3. OpenClaw `session_get` still had no first-class planning handoff summary

After this batch:

1. the checkpoint itself carries a stronger handoff artifact
2. retrieval and writeback now share the same evidence vocabulary
3. session payload no longer requires plugin callers to spelunk `control_plane` just to recover the planning handoff

## Validation

Passed:

1. `python3 -m py_compile chatgptrest/planning/meeting_task_store.py chatgptrest/api/routes_agent_v3.py scripts/planning_task_checkpoint_get.py scripts/planning_task_checkpoint_list.py scripts/planning_task_checkpoint_writeback.py scripts/planning_task_checkpoint_complete.py tests/test_meeting_task_store.py tests/test_planning_task_checkpoint_query.py tests/test_planning_task_checkpoint_writeback.py tests/test_planning_task_checkpoint_complete.py tests/test_routes_agent_v3_planning_task_plane.py`
2. `./.venv/bin/pytest -q tests/test_meeting_task_store.py tests/test_planning_task_checkpoint_query.py tests/test_planning_task_checkpoint_writeback.py tests/test_planning_task_checkpoint_complete.py tests/test_routes_agent_v3_planning_task_plane.py tests/test_openclaw_cognitive_plugins.py`

## Current boundary after this batch

What is now true:

1. `W2-S3` is landed in code, not only a design note
2. planning handoff can now be read from REST task payload, session payload, CLI query, and OpenClaw summary with the same core fields
3. writeback can now explicitly record stable facts, pending actions, next recommended step, and evidence refs

What is still not done:

1. lane policy is still not yet a runtime-visible policy contract
2. attachment preflight is still a projected posture, not yet the final fail-closed action policy
3. `W3-W6` remain pending after this batch
