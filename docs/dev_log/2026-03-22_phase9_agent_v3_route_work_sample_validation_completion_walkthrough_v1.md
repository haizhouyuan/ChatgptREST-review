# Phase 9 Agent V3 Route Work Sample Validation Completion Walkthrough v1

## What Changed

Added a new route-level validation layer on top of the earlier semantic packs.

Instead of only checking front-door semantic normalization, this phase replays
the live `/v3/agent/turn` route with a fake controller and records:

- captured `task_intake`
- captured `scenario_pack`
- strategist output
- final public response route/status
- actual branch taken: `controller` vs `clarify`

## Key Decisions

1. Did not expand to OpenClaw dynamic replay.
   The OpenClaw TypeScript extension still requires a separate JS runtime setup,
   so this phase stays inside Python and freezes the public REST front door first.

2. Did not patch live route code.
   The validator is additive and uses runtime patching around the live router,
   which keeps blast radius low.

3. Corrected dataset expectations instead of changing production logic.
   The first run showed four failures, but all were due to incorrect expected
   `output_shape` values in the dataset:
   - `meeting_summary` / `interview_notes` packs legitimately emit `meeting_summary`
   - `topic_research` / `comparative_research` packs legitimately emit `research_memo`

## Evidence

Generated artifacts:

- [report_v1.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/phase9_agent_v3_route_work_sample_validation_20260322/report_v1.json)
- [report_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/phase9_agent_v3_route_work_sample_validation_20260322/report_v1.md)

Final runner result:

- `items=7`
- `passed=7`
- `failed=0`

## Commit Trail

- `21567f1` `feat: add phase9 agent v3 route work sample validation`
- current docs commit records the phase completion and artifacts

