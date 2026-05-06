# Red-Team Followup Plan Corrections Walkthrough V1

Date: 2026-04-08

## What changed

I updated the next-wave planning artifacts after rechecking the red-team claims against current HEAD.

Added:

- [Refined Next-Stage Full Execution Plan V3](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-08_refined_next_stage_full_execution_plan_v3.md)
- [Residual Gap And Risk Note V2](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-08_residual_gap_and_risk_note_v2.md)
- [Next-Stage Execution TODO Master V10](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-04-08_next_stage_execution_todo_master_v10.md)

## What was absorbed

Four points were promoted into the next-wave plan:

1. explicit lifecycle decision for `advisor_agent_*` vs `coding_agent_*`
2. one live Deep Research finality gate
3. explicit precondition pack before any live `scope_project` backfill
4. dedicated promotion root-cause diagnosis

## What was corrected

Two red-team claims were not carried forward because current HEAD no longer matches them:

1. `engine.py` is already completion-contract-aware
2. `advisor_agent_status/wait` already inherit completion-contract fields through the public session projection path

## Why this matters

Without these corrections, the next wave would risk solving stale problems instead of the current real ones:

- surface governance
- live finality proof
- write safety before live backfill
- promotion root-cause diagnosis
