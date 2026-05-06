# Refined Next-Stage Full Execution Plan V5

Date: 2026-04-08

Supersedes:

- [Refined Next-Stage Full Execution Plan V4](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-08_refined_next_stage_full_execution_plan_v4.md)

Related frozen records:

- [Red-Team Follow-On Wave Completion Summary V1](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-08_red_team_followon_wave_completion_summary_v1.md)
- [Live Deep Research Finality Gate Completion V1](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-08_live_deep_research_finality_gate_completion_v1.md)
- [Scope Project Live Backfill Readiness Decision V1](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-08_scope_project_live_backfill_readiness_decision_v1.md)
- [Promotion Low-Active Root-Cause Diagnosis V1](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-08_promotion_low_active_root_cause_diagnosis_v1.md)

## 1. Why V5 exists

V4 correctly identified the systemic coherence problems, but the latest runtime review made one thing clear:

> the platform is architecturally coherent enough to continue, but it is still not product-grade until the remaining runtime hard blockers are cleared.

The blockers are now concrete:

1. `coding_agent_answer` still reaches green through `last_answer_fallback` instead of a healthy jobs-answer primary path.
2. the reviewed planning-review maintenance unit exists in repo, but is not installed in the live user systemd runtime.
3. one route-validation test is red because the dataset still encodes stale behavior for the workforce-planning funnel lane.
4. the public MCP runtime has no direct `/health` endpoint, which leaves monitoring blind at the exact ingress layer we now treat as the default coding-agent surface.

V5 is therefore not another architecture wave.

It is a **productionization corrective wave**.

## 2. V5 objective

V5 is complete only when the current default coding-agent lane is not just contract-correct, but operationally production-ready.

That means:

1. the canonical answer primary path works with the intended auth domain
2. fallback remains available, but is visibly degraded rather than silently normal
3. the promotion maintenance scheduler is actually installed and running
4. the default MCP ingress has an explicit health surface
5. the route-validation suite no longer fails on stale expectations

## 3. Current frozen facts

These remain true and are not reopened by V5:

1. `coding_agent_*` remains the default mature public lane.
2. `advisor_agent_*` remains the broader advisor / compatibility lane.
3. `scope_project` live broad write is still deferred.
4. promotion throughput tuning is still blocked until scheduling is live and evidenced.

## 4. Work package Q: jobs-answer primary-path repair

### Objective

Make the jobs-answer API the healthy primary retrieval path for public coding-agent answer fetches.

### Root cause

The current MCP runtime uses one helper source for two auth domains:

- `/v3/agent/*` can accept `OPENMIND_API_KEY`
- `/v1/jobs/*` requires bearer auth with `CHATGPTREST_API_TOKEN` or `CHATGPTREST_OPS_TOKEN`

As a result, `_job_answer()` can still send the wrong credential type and hit `401 unauthorized`.

### Required implementation

1. Split public-agent and jobs bearer token helpers in [agent_mcp.py](/vol1/1000/projects/ChatgptREST/chatgptrest/mcp/agent_mcp.py).
2. Route session/status calls through the OpenMind/public-agent auth helper.
3. Route `/v1/jobs/{job_id}/answer` calls through the jobs bearer helper only.
4. Expose degraded-mode state clearly when fallback is used.
5. Add tests that prove:
   - the jobs API uses bearer auth sourced from the jobs token helper
   - unauthorized jobs API responses fall back cleanly and explicitly

### Acceptance

1. A correctly provisioned live runtime returns `source=job_answer_api` from `coding_agent_answer`.
2. A deliberately degraded runtime still returns `source=last_answer_fallback`, and the degraded reason is explicit.
3. There is no longer a shared helper that silently treats `OPENMIND_API_KEY` as a jobs bearer token.

## 5. Work package R: public MCP observability completion

### Objective

Give the default public MCP ingress a first-class health endpoint and make it visible to operations.

### Required implementation

1. Add a custom `/health` route on the public agent MCP server.
2. Return a narrow, non-sensitive payload that at minimum states:
   - `ok`
   - transport / surface identity
   - auth-mode summary
   - primary-path readiness vs degraded fallback readiness
3. Add a test for the custom route.
4. Include the new endpoint in runtime validation or monitoring docs where appropriate.

### Acceptance

1. `curl http://127.0.0.1:18712/health` returns `200`.
2. The response is usable for monitoring without exposing secrets.
3. The response can distinguish a healthy primary-path runtime from a degraded fallback runtime.

## 6. Work package S: promotion maintenance scheduler recovery

### Objective

Move planning-review maintenance from “repo contains a reviewed timer” to “live runtime actually runs it”.

### Required implementation

1. Install the reviewed unit pair into the live user systemd runtime:
   - [chatgptrest-planning-review-maintenance.service](/vol1/1000/projects/ChatgptREST/ops/systemd/chatgptrest-planning-review-maintenance.service)
   - [chatgptrest-planning-review-maintenance.timer](/vol1/1000/projects/ChatgptREST/ops/systemd/chatgptrest-planning-review-maintenance.timer)
2. Enable and start the timer.
3. Capture evidence that:
   - the unit is installed
   - the timer is enabled
   - at least one maintenance run occurs
4. Rerun promotion inventory after maintenance has had a chance to advance.

### Acceptance

1. `systemctl --user list-unit-files` shows the planning-review maintenance timer installed.
2. `systemctl --user list-timers` or equivalent evidence shows it scheduled.
3. A maintenance run produces fresh evidence artifacts after enablement.

## 7. Work package T: route-validation suite correction

### Objective

Restore a green route-validation suite by aligning stale workforce-planning expectations with current funnel-lane semantics.

### Required implementation

1. Inspect the failing case in [phase9_agent_v3_route_work_samples_v1.json](/vol1/1000/projects/ChatgptREST/eval_datasets/phase9_agent_v3_route_work_samples_v1.json).
2. Decide whether the bug is in:
   - current routing behavior
   - or the dataset expectation
3. Apply the narrower correction.
4. Re-run the route-validation test and ensure it is green.

### Acceptance

1. `tests/test_agent_v3_route_work_sample_validation.py` passes.
2. The correction is consistent with current planning/funnel semantics.
3. The fix does not reopen earlier route-work sample coverage.

## 8. Work package U: live production-readiness revalidation

### Objective

Run one final productionization validation pass after Q-R-S-T land.

### Required implementation

1. Re-run the live Deep Research finality gate.
2. Confirm whether the answer source is now primary-path or degraded-path.
3. Hit the new MCP `/health` endpoint directly.
4. Re-run the targeted tests touched by this corrective wave.
5. Record one completion summary with:
   - what is now production-ready
   - what remains intentionally deferred

### Acceptance

1. Live gate evidence exists for the post-fix runtime.
2. MCP health evidence exists.
3. All targeted tests for this wave pass.
4. Residual risk notes clearly separate:
   - fixed production blockers
   - intentionally deferred strategic work

## 9. Execution order

V5 executes in this order:

1. `Q` jobs-answer primary-path repair
2. `R` public MCP health completion
3. `S` promotion maintenance scheduler recovery
4. `T` route-validation suite correction
5. `U` live production-readiness revalidation

## 10. Explicit non-goals

V5 does not include:

1. broad `scope_project` live backfill
2. promotion threshold tuning
3. another large surface redesign
4. retirement of `advisor_agent_*`

Those remain separate decisions after this productionization wave is complete.
