# 2026-04-05 Claude G AC Planning Agent Mature Stability Gap Plan Redteam v1

## Scope

Red-team target:

- `docs/reviews/2026-04-05_planning_agent_mature_stability_gap_analysis_and_completion_plan_v1.md`

Primary context read by `Claude G AC`:

- `docs/reviews/2026-04-03_planning_agent_full_unfinished_implementation_plan_v7.md`
- `docs/reviews/2026-04-03_planning_agent_new_session_handoff_v2.md`
- `docs/reviews/2026-04-04_planning_agent_total_plan_execution_master_v59.md`
- `docs/reviews/2026-04-04_w1_live_triage_and_task_truth_alignment_execution_review_v1.md`
- `docs/reviews/2026-04-04_w1_chatgpt_live_lane_unblock_and_completion_execution_review_v1.md`
- `docs/reviews/2026-04-04_w4_planning_knowledge_ingress_and_memory_writeback_execution_review_v1.md`
- `docs/reviews/2026-04-04_w5_planning_task_plane_p0_acceptance_execution_review_v1.md`
- `docs/reviews/2026-04-04_w6_planning_truth_surface_consolidation_execution_review_v1.md`

Run record:

- `runner`: `claudegac`
- `run_id`: `ccjob_20260405T004712Z_21cdf597`
- `status`: `succeeded`
- `duration_sec`: `379`
- result artifact: `/vol1/1000/home-yuanhaizhou/.claude-gac/skills/claudecode-agent-runner/runs/ccjob_20260405T004712Z_21cdf597/result/claude_result.json`

## Red-Team Verdict

`Claude G AC` verdict:

- the gap diagnosis is materially correct
- the proposed tranche direction is right
- but the tranche is only conditionally approvable
- acceptance must be tightened to prevent fake closure

## What Claude Confirmed

1. `G2` is real and critical.
   The committed `7/7 + branch` pack predates `W2-W6`.
2. `G3` is real.
   `planning_query` exists at the plugin layer but not on the server REST layer.
3. Gap ordering is directionally correct.
   `G1/G2/G3` are the real blockers; policy/runtime-pack governance is lower priority for this closure batch.

## Red-Team Corrections

1. The current `5/5` P0 pack is synthetic on knowledge/writeback.
   It patches `_maybe_apply_planning_knowledge_ingress` and `_maybe_writeback_planning_work_memory`, so it does not prove real end-to-end `W4` behavior.
2. The current `7/7` pack is also synthetic in controller/runtime scope.
   It patches `ControllerEngine` and `_advisor_runtime`, so a rebind still needs an explicit scope statement.
3. The old `3/3` continuity pack was never committed to git.
   It exists on disk but is not a version-frozen baseline.
4. `G4` was understated.
   A mature-stability closure should not leave work-memory writeback only on session/control-plane if the gate still claims phase-1 mainline writeback.

## Required Tightening

`Claude G AC` required the execution tranche to include:

1. A fresh current-code `Gemini` live completion gate run.
2. A fresh current-code cancel consistency probe.
3. At least one `P0` scenario without patched knowledge ingress / memory writeback.
4. A committed fresh `3/3` continuity pack.
5. Either fresh `ChatGPT` live re-validation or an explicit exclusion from the mature-stability claim.
6. Server-side tests for `planning_query` on REST surfaces.

## My Decision

I accept the red-team tightening in full.

This means the executable closure batch is no longer:

1. only rebind old offline packs
2. only add server truth projection
3. only export a unified manifest

It must instead:

1. refresh live evidence first
2. fix server/CLI truth projection
3. make writeback truth durable
4. re-export all offline packs on current code
5. bind everything into one fail-closed mature-stability manifest

## Execution Consequence

The next authoritative todo list is:

- `docs/reviews/2026-04-05_planning_agent_mature_stability_execution_todolist_v1.md`
