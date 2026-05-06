# Promotion Low-Active Root-Cause Diagnosis Walkthrough V1

Date: 2026-04-08

## What I did

I turned the promotion section of the next-stage preflight evidence pack into an explicit root-cause diagnosis document.

Inputs used:

- [preflight summary json](/vol1/1000/projects/ChatgptREST/artifacts/monitor/next_stage_preflight/20260407T224249Z/preflight_summary.json)
- [preflight summary md](/vol1/1000/projects/ChatgptREST/artifacts/monitor/next_stage_preflight/20260407T224249Z/preflight_summary.md)

Output:

- [Promotion Low-Active Root-Cause Diagnosis V1](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-08_promotion_low_active_root_cause_diagnosis_v1.md)

## Why this matters

Before this note, the repo had:

- promotion inventory
- maintenance harness
- preflight evidence

But it still lacked one explicit sentence answering:

`What is the dominant reason active coverage is still so low?`

The answer, based on the current evidence, is:

- scheduling absence first
- gate tuning second, if needed later

## Resulting constraint

This means future work should not jump straight to threshold or cleanup changes.

The system should first prove that reviewed promotion is actually scheduled and moving again.
