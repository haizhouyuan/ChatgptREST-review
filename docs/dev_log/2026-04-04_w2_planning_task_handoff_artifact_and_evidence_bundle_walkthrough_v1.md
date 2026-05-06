# 2026-04-04 W2 planning task handoff artifact and evidence bundle walkthrough v1

## What I changed

I finished the missing `W2-S3` shape work instead of only tightening access and read semantics around the old shape:

1. checkpoint now stores structured handoff fields
2. query/writeback/session/plugin surfaces now all project the same handoff payload
3. session public payload now exposes a top-level `planning_task` alias with enriched handoff

## Why this batch was necessary

The previous state still forced the next surface to guess intent from mixed fields:

1. `confirmed_scope` and `next_actions` existed, but there was no explicit “stable facts vs pending actions” split
2. `artifact_refs` existed, but there was no explicit writeback-evidence lane
3. session payload contained planning state, but callers still had to dig through `control_plane` and reconstruct the handoff

This was exactly the gap that kept `W2` unfinished.

## Files changed

1. [meeting_task_store.py](/vol1/1000/projects/ChatgptREST/chatgptrest/planning/meeting_task_store.py)
2. [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py)
3. [planning_task_checkpoint_get.py](/vol1/1000/projects/ChatgptREST/scripts/planning_task_checkpoint_get.py)
4. [planning_task_checkpoint_list.py](/vol1/1000/projects/ChatgptREST/scripts/planning_task_checkpoint_list.py)
5. [planning_task_checkpoint_writeback.py](/vol1/1000/projects/ChatgptREST/scripts/planning_task_checkpoint_writeback.py)
6. [planning_task_checkpoint_complete.py](/vol1/1000/projects/ChatgptREST/scripts/planning_task_checkpoint_complete.py)
7. [index.ts](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-advisor/index.ts)
8. [AGENTS.md](/vol1/1000/projects/ChatgptREST/AGENTS.md)

## Behavior after the change

1. planning task public payload now includes:
   - `handoff.stable_facts`
   - `handoff.pending_actions`
   - `handoff.last_completed_step`
   - `handoff.next_recommended_step`
   - `handoff.writeback_evidence`
   - `handoff.evidence_bundle`
   - `handoff.writeback_contract`
2. old records still read cleanly because compatibility projection fills the new handoff view from legacy checkpoint fields
3. CLI writeback/complete can now explicitly write the new handoff fields
4. `session_get` can now be consumed without a second parser layer for planning task handoff

## Verification

Passed:

1. `python3 -m py_compile chatgptrest/planning/meeting_task_store.py chatgptrest/api/routes_agent_v3.py scripts/planning_task_checkpoint_get.py scripts/planning_task_checkpoint_list.py scripts/planning_task_checkpoint_writeback.py scripts/planning_task_checkpoint_complete.py tests/test_meeting_task_store.py tests/test_planning_task_checkpoint_query.py tests/test_planning_task_checkpoint_writeback.py tests/test_planning_task_checkpoint_complete.py tests/test_routes_agent_v3_planning_task_plane.py`
2. `./.venv/bin/pytest -q tests/test_meeting_task_store.py tests/test_planning_task_checkpoint_query.py tests/test_planning_task_checkpoint_writeback.py tests/test_planning_task_checkpoint_complete.py tests/test_routes_agent_v3_planning_task_plane.py tests/test_openclaw_cognitive_plugins.py`

## Next

`W2` 的 schema/handoff 主体已经收住。后续应转入 `W3`：

1. 先把 lane policy 变成 runtime-visible contract
2. 再把 attachment preflight 从 advisory posture 提升到更稳定的 action contract
