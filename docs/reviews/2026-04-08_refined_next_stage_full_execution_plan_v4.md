# Refined Next-Stage Full Execution Plan V4

Date: 2026-04-08

Supersedes:

- [Refined Next-Stage Full Execution Plan V3](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-08_refined_next_stage_full_execution_plan_v3.md)

Related frozen records:

- [Public Lane Lifecycle Decision V1](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-08_public_lane_lifecycle_decision_v1.md)
- [Live Deep Research Finality Gate Completion V1](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-08_live_deep_research_finality_gate_completion_v1.md)
- [Scope Project Live Backfill Readiness Decision V1](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-08_scope_project_live_backfill_readiness_decision_v1.md)
- [Promotion Low-Active Root-Cause Diagnosis V1](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-08_promotion_low_active_root_cause_diagnosis_v1.md)
- [Red-Team Follow-On Wave Completion Summary V1](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-08_red_team_followon_wave_completion_summary_v1.md)

## 1. Why V4 exists

V3 and the red-team follow-on wave completed successfully.

They clarified the platform boundary and closed the immediate public-lane defects, but they also exposed the next deeper systemic problem:

> the platform now works through a mix of narrow-lane contract, compatibility-lane contract, fallback behavior, and runtime maintenance tooling, but the root invariants are still not fully unified.

The clearest example is the `jobs answer 401` issue:

- public coding-agent behavior is now correct
- but it is correct partly because `last_answer_fallback` masks an auth-domain mismatch

That means the platform is usable but not yet fully coherent.

V4 is the first plan whose scope is not “finish the corrective wave”.

Its scope is:

> make the public surface, auth domains, runtime gates, project truth, and promotion maintenance internally consistent enough that the same class of problems does not recur under a different name.

## 2. Current state summary

These are now treated as frozen facts:

1. `coding_agent_*` is the default narrow public lane for mature coding agents.
2. `advisor_agent_*` remains the broader public advisor / compatibility lane.
3. The live Deep Research finality gate is green.
4. That green result currently uses `last_answer_fallback`, not a guaranteed readable jobs-answer primary path.
5. `scope_project` runtime use is live, but production backfill remains deferred.
6. Promotion low-active coverage is currently dominated by scheduling absence, not proven gate strictness.

## 3. V4 objective

V4 is a **systemic coherence and runtime hardening program**.

Its goal is to make these five layers consistent with one another:

1. public coding-agent contract
2. broad advisor compatibility contract
3. internal auth domains and service env
4. project-scoped truth and controlled write-back
5. promotion maintenance as a real running subsystem

## 4. Success criteria

V4 is complete only when all of the following are true:

1. `coding_agent_answer` can succeed on the intended primary path when the service is correctly provisioned.
2. Fallback remains available, but is explicitly treated as degraded mode rather than the normal happy path.
3. Public lane auth rules are explicit, testable, and fail-fast at startup when misconfigured.
4. `scope_project` live write still does not run until mismatch families are adjudicated, but there is now a concrete resolution path instead of indefinite deferral.
5. Promotion maintenance is actually scheduled and observable in the live runtime.
6. The release gate pack includes both:
   - contract / harness checks
   - live operational checks for the subsystems that previously drifted silently

## 5. Work package K: Auth-domain separation and public-lane primary-path repair

### Objective

Remove the implicit token mixing between:

- OpenMind / public advisor-agent auth
- Jobs API bearer auth

and restore a clean primary path for public answer retrieval.

### Root cause to eliminate

Current code uses one `_api_key()` source for two different domains:

- `/v3/agent/*` can accept `OPENMIND_API_KEY`
- `/v1/jobs/*` expects `CHATGPTREST_API_TOKEN` or `CHATGPTREST_OPS_TOKEN`

That is why `_job_answer()` can still hit `401 unauthorized` even while session reads succeed.

### Required implementation

1. Split the token helpers in [agent_mcp.py](/vol1/1000/projects/ChatgptREST/chatgptrest/mcp/agent_mcp.py):
   - `_openmind_api_key()`
   - `_jobs_bearer_token()`
   - optionally `_jobs_ops_token()` if fallback support remains intentional
2. Ensure each internal HTTP helper uses the correct source:
   - session / advisor routes use `X-Api-Key` or bearer as documented
   - jobs routes use bearer token only
3. Add one startup/runtime self-check for the public MCP service:
   - if coding-agent answer support is enabled
   - and jobs primary-path token is absent
   - surface this as an explicit degraded-mode warning or fail-fast state
4. Update service/runbook docs so the intended env contract is explicit.

### Files likely involved

- [chatgptrest/mcp/agent_mcp.py](/vol1/1000/projects/ChatgptREST/chatgptrest/mcp/agent_mcp.py)
- [ops/start_mcp.sh](/vol1/1000/projects/ChatgptREST/ops/start_mcp.sh)
- systemd unit / env material for `chatgptrest-mcp.service`
- [docs/runbook.md](/vol1/1000/projects/ChatgptREST/docs/runbook.md)
- [AGENTS.md](/vol1/1000/projects/ChatgptREST/AGENTS.md)

### Acceptance

1. A correctly provisioned public MCP runtime returns `source=job_answer_api` for the live canonical answer path.
2. A deliberately degraded runtime still returns `source=last_answer_fallback`, and the degraded reason is explicit.
3. There is no longer a shared helper that silently treats `OPENMIND_API_KEY` as a jobs bearer token.
4. Startup or self-check evidence makes the degradation visible before client traffic discovers it.

## 6. Work package L: Public-surface governance and lane simplification

### Objective

Keep the current lane separation, but make the lifecycle and client guidance impossible to misread.

### Required implementation

1. Freeze one authoritative statement of lane roles:
   - `coding_agent_*` = default mature coding-agent lane
   - `advisor_agent_*` = compatibility / broad advisor lane
2. Add one explicit deprecation policy section:
   - what is stable
   - what is compatibility-only
   - what would require a future migration notice
3. Ensure wrappers / skills / docs do not continue to present both lanes as equally primary for coding clients.
4. Add one machine-readable lane policy artifact or registry entry that can be checked by gate scripts.

### Files likely involved

- [ops/registries/surface_policy.yaml](/vol1/1000/projects/ChatgptREST/ops/registries/surface_policy.yaml)
- [skills-src/chatgptrest-call/SKILL.md](/vol1/1000/projects/ChatgptREST/skills-src/chatgptrest-call/SKILL.md)
- [docs/contract_v1.md](/vol1/1000/projects/ChatgptREST/docs/contract_v1.md)
- [AGENTS.md](/vol1/1000/projects/ChatgptREST/AGENTS.md)

### Acceptance

1. A maintainer can tell the default lane, compatibility lane, and deprecated lane status from one document set.
2. The release gate can detect if docs regress into presenting both lanes as co-equal defaults.

## 7. Work package M: Live gate pack hardening

### Objective

Turn the current release gate from “green on contract plus one live finality proof” into a runtime pack that explicitly distinguishes:

- happy path
- degraded but supported path
- misconfigured path

### Required implementation

1. Extend the live Deep Research finality gate:
   - record whether answer retrieval used primary path or fallback path
   - treat fallback as green only if degradation is explicitly allowed by policy
2. Add one auth-domain smoke:
   - session read path
   - jobs answer path
   - both observed in the same runtime
3. Add one maintenance presence check:
   - promotion maintenance timer/service installed and visible
4. Fold these checks into the release gate pack or make them explicit blocking companions.

### Files likely involved

- [ops/run_live_deep_research_finality_gate.py](/vol1/1000/projects/ChatgptREST/ops/run_live_deep_research_finality_gate.py)
- [ops/run_next_stage_release_gate_pack.py](/vol1/1000/projects/ChatgptREST/ops/run_next_stage_release_gate_pack.py)
- [ops/next_stage_release_gate_pack_manifest_v1.json](/vol1/1000/projects/ChatgptREST/ops/next_stage_release_gate_pack_manifest_v1.json)
- relevant tests under [tests](/vol1/1000/projects/ChatgptREST/tests)

### Acceptance

1. The gate distinguishes:
   - `primary_path_green`
   - `degraded_path_green`
   - `misconfigured_red`
2. The gate fails if the runtime silently falls into a degraded auth state without surfacing it.
3. The gate fails if promotion maintenance scheduling is absent where policy requires it.

## 8. Work package N: `scope_project` mismatch-family adjudication and controlled write path

### Objective

Replace indefinite deferral with a controlled human-in-the-loop resolution path for `scope_project`.

### Required implementation

1. Produce one adjudication note for the two dominant mismatch families:
   - `planning` atom scope vs `research` document project
   - `multi` atom scope vs `ChatgptREST` document project
2. Define the canonical project namespace policy:
   - blank values
   - path-like values
   - dated low-volume labels
   - multi-project semantics
3. Generate a narrowed dry-run candidate set limited to rows that are provably safe.
4. Keep live write blocked until the above are explicitly reviewed.

### Files likely involved

- [scripts/backfill_evomap_scope_project.py](/vol1/1000/projects/ChatgptREST/scripts/backfill_evomap_scope_project.py)
- evidence under [artifacts/monitor/next_stage_preflight](/vol1/1000/projects/ChatgptREST/artifacts/monitor/next_stage_preflight)
- new review notes under [docs/reviews](/vol1/1000/projects/ChatgptREST/docs/reviews)

### Acceptance

1. The team can explain what each mismatch family means before any write is attempted.
2. A dry-run report enumerates exactly which rows would be touched.
3. No broad live backfill is allowed without that reviewed dry-run.

## 9. Work package O: Promotion maintenance recovery

### Objective

Make promotion maintenance a live operational subsystem rather than a dormant design.

### Required implementation

1. Install or enable the repo’s reviewed maintenance unit(s) in the live runtime.
2. Record evidence that the timer/service actually runs.
3. Rerun inventory after maintenance has advanced.
4. Only after that, decide whether threshold tuning or throughput tuning is justified.

### Files likely involved

- [ops/systemd/chatgptrest-planning-review-maintenance.service](/vol1/1000/projects/ChatgptREST/ops/systemd/chatgptrest-planning-review-maintenance.service)
- [ops/systemd/chatgptrest-planning-review-maintenance.timer](/vol1/1000/projects/ChatgptREST/ops/systemd/chatgptrest-planning-review-maintenance.timer)
- [ops/run_planning_review_maintenance.py](/vol1/1000/projects/ChatgptREST/ops/run_planning_review_maintenance.py)
- [ops/report_evomap_promotion_inventory.py](/vol1/1000/projects/ChatgptREST/ops/report_evomap_promotion_inventory.py)

### Acceptance

1. `systemctl --user list-timers` or equivalent evidence shows the reviewed maintenance timer live.
2. A post-enable inventory shows movement in `promotion_audit` recency.
3. Any future tuning proposal cites post-maintenance evidence, not pre-maintenance assumptions.

## 10. Work package P: Authority and runtime-truth governance completion

### Objective

Keep authority anchor, project runtime truth, and public lane semantics aligned.

### Required implementation

1. Add schema-level governance for authority anchors:
   - required fields
   - stale handling
   - ownership metadata
2. Ensure public lane runtime truth never outranks authority anchor decisions.
3. Add one release gate that fails if authority docs are missing, stale, or structurally invalid.

### Files likely involved

- authority governance modules already added in the boundary-consolidation release
- [AGENTS.md](/vol1/1000/projects/ChatgptREST/AGENTS.md)
- [docs/runbook.md](/vol1/1000/projects/ChatgptREST/docs/runbook.md)
- authority audit/release gate scripts

### Acceptance

1. Authority anchor remains the top priority truth source.
2. Missing or stale authority material is visible as a release/gate issue, not silent drift.

## 11. Execution order

V4 should execute in this order:

1. `K` auth-domain separation and primary-path repair
2. `M` live gate hardening
3. `L` public-surface governance completion
4. `O` promotion maintenance recovery
5. `N` scope_project adjudication + dry-run narrowing
6. `P` authority/runtime governance completion

Rationale:

- `K` and `M` remove the highest-leverage runtime incoherence first.
- `O` should happen before any promotion tuning discussion.
- `N` should happen before any scope-project live write discussion.
- `P` hardens the truth layer after the runtime semantics are stabilized.

## 12. Explicit non-goals for V4

V4 does **not** include:

- broad substrate redesign
- generic new advisor features
- bulk document cleanup campaigns
- large-scale promotion threshold experiments
- broad live `scope_project` normalization

## 13. Exit condition

V4 is complete when:

1. auth domains are explicitly separated in code and runtime config
2. public answer retrieval has a validated primary path and an explicit degraded path
3. public lane governance is machine-checkable
4. promotion maintenance is running and evidenced
5. scope-project live write remains blocked until mismatch families are adjudicated, but the adjudication path itself is fully specified
6. authority/runtime truth governance is release-blocking rather than advisory only

At that point, the platform will no longer be in a state where “one hidden runtime mismatch is silently masked by a fallback and only discovered by live gate work”.
