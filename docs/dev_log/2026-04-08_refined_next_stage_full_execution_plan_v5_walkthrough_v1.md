# Refined Next-Stage Full Execution Plan V5 Walkthrough V1

Date: 2026-04-08

Companion:

- [Refined Next-Stage Full Execution Plan V5](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-08_refined_next_stage_full_execution_plan_v5.md)

## Why this version exists

V4 already captured the systemic coherence problem correctly.

This walkthrough records why a narrower V5 wave was necessary:

1. runtime review showed the default coding-agent lane was architecturally correct but still not fully product-grade
2. the remaining blockers were not broad architecture gaps, but productionization gaps
3. the right response was therefore to define one short corrective wave with explicit acceptance gates

## What changed from V4 to V5

V5 narrows the active execution wave to five items:

1. repair jobs-answer primary-path auth coherence
2. add MCP `/health`
3. install and evidence the reviewed planning-review maintenance timer
4. clear the red route-validation test
5. re-run live validation on the corrected runtime

## Why these are the right next tasks

Each one maps directly to a real runtime symptom:

- `401 unauthorized` on `/v1/jobs/{job_id}/answer`
- no direct health endpoint on `18712`
- reviewed maintenance unit exists but is not installed live
- one concrete red test remains
- green gate still proves degraded success rather than full primary-path success

## Expected output of this wave

At the end of V5, we should be able to say:

1. the default coding-agent lane is product-ready for the currently supported flow
2. degraded fallback is still present, but no longer masquerades as the normal happy path
3. maintenance and observability gaps for the public lane are closed
