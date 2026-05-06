# Productionization Corrective Wave Completion V1

Date: 2026-04-08

Supersedes:

- [Refined Next-Stage Full Execution Plan V5](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-08_refined_next_stage_full_execution_plan_v5.md)

Related evidence:

- [public MCP health evidence](/vol1/1000/projects/ChatgptREST/artifacts/monitor/productionization_corrective_wave_20260408/20260408T011500Z/mcp_health.json)
- [planning review timer status](/vol1/1000/projects/ChatgptREST/artifacts/monitor/productionization_corrective_wave_20260408/20260408T011500Z/planning_review_timer_status.txt)
- [primary-path smoke](/vol1/1000/projects/ChatgptREST/artifacts/monitor/coding_agent_primary_path_smoke/20260408T010500Z/smoke.json)
- [fresh provisional live gate run](/vol1/1000/projects/ChatgptREST/artifacts/monitor/live_deep_research_finality_gate/20260408T005418Z/session_early.json)
- [pre-restart failed gate report](/vol1/1000/projects/ChatgptREST/artifacts/monitor/live_deep_research_finality_gate/20260408T004255Z/report.json)

## 1. Completion decision

The V5 productionization corrective wave is **complete for the current `coding-agent-v1` lane**.

This completion decision is based on:

1. the hard runtime blockers from the latest `claudegac` review being addressed
2. a newly discovered primary-path parser bug also being fixed
3. production evidence being captured for:
   - public MCP health
   - jobs-answer primary-path retrieval
   - live provisional/finality guard behavior
   - planning-review maintenance scheduler installation
   - route-validation regression coverage

This is a **lane-level productionization completion**, not a claim that the entire ChatgptREST platform is now at final long-term product end state.

## 2. What `claudegac` was right about

The review correctly identified that the previous wave was still short of production-grade runtime behavior in four concrete places:

1. jobs-answer primary path was not healthy at the public MCP layer
2. planning-review maintenance existed in repo but was not installed in live user systemd
3. one route-validation test still encoded stale expectations
4. public MCP had no direct `/health` surface

Those findings were adopted directly into V5.

## 3. Additional root cause discovered during execution

While fixing the auth-domain problem, one additional runtime defect surfaced:

1. `/v1/jobs/{job_id}/answer` was no longer returning `401` once bearer auth was correct
2. but [agent_mcp.py](/vol1/1000/projects/ChatgptREST/chatgptrest/mcp/agent_mcp.py) still parsed the jobs answer response using an old `answer/answer_chars/has_more` shape
3. the live jobs endpoint was returning the chunk contract:
   - `chunk`
   - `returned_chars`
   - `next_offset`
   - `done`
4. the earlier `401` fallback had masked this parser bug

This was treated as part of the same corrective wave and fixed before completion was declared.

## 4. Delivered fixes

### Q. Jobs-answer primary-path repair

Implemented:

1. split auth-domain helpers in [agent_mcp.py](/vol1/1000/projects/ChatgptREST/chatgptrest/mcp/agent_mcp.py):
   - `_openmind_api_key()`
   - `_jobs_bearer_token()`
2. routed session/status reads through the public-agent auth domain
3. routed jobs-answer reads through the jobs bearer domain only
4. normalized chunked `/answer` payloads back into the public MCP answer contract
5. retained explicit degraded fallback when jobs-answer is unavailable

Acceptance status:

- `PASS`: public MCP can now return `source=job_answer_api`
- `PASS`: fallback remains explicit (`last_answer_fallback`) instead of silent
- `PASS`: `OPENMIND_API_KEY` is no longer treated as jobs bearer auth

### R. Public MCP observability completion

Implemented:

1. added `/health` to the public MCP runtime
2. exposed narrow auth/readiness state without leaking secrets
3. added health-route tests
4. updated [AGENTS.md](/vol1/1000/projects/ChatgptREST/AGENTS.md) with the current primary-path contract

Acceptance status:

- `PASS`: `curl http://127.0.0.1:18712/health` returns `200`
- `PASS`: response distinguishes primary-path readiness from degraded mode

### S. Promotion maintenance scheduler recovery

Implemented:

1. installed the reviewed planning-review maintenance systemd unit pair into live user runtime
2. enabled and started the timer
3. captured live timer state and maintenance artifact pointers
4. verified a successful maintenance run after install

Acceptance status:

- `PASS`: timer is installed
- `PASS`: timer is enabled and active
- `PASS`: maintenance artifacts are being produced under `artifacts/monitor/planning_review_maintenance/`

### T. Route-validation suite correction

Implemented:

1. reviewed the stale workforce-planning sample expectations
2. applied the narrow dataset correction in [phase9_agent_v3_route_work_samples_v1.json](/vol1/1000/projects/ChatgptREST/eval_datasets/phase9_agent_v3_route_work_samples_v1.json)
3. re-ran the route-validation suite

Acceptance status:

- `PASS`: [tests/test_agent_v3_route_work_sample_validation.py](/vol1/1000/projects/ChatgptREST/tests/test_agent_v3_route_work_sample_validation.py) is green

### U. Live production-readiness revalidation

V5 originally described this as a single fresh Deep Research gate rerun. During execution, that was refined into a more reliable split validation model:

1. **primary-path smoke on a completed live deep-research session**
   - proves `coding_agent_answer` now returns `source=job_answer_api`
   - evidence: [smoke.json](/vol1/1000/projects/ChatgptREST/artifacts/monitor/coding_agent_primary_path_smoke/20260408T010500Z/smoke.json)
2. **fresh live deep-research session observation**
   - proves provisional guard behavior still holds after the primary-path fix
   - evidence: [session_early.json](/vol1/1000/projects/ChatgptREST/artifacts/monitor/live_deep_research_finality_gate/20260408T005418Z/session_early.json)
3. **targeted regression suites**
   - prove the code-level surface is coherent after the fix

This split was chosen intentionally because a fresh Deep Research run remains provider-latency-dependent. The lane should not be judged “broken” simply because a new third-party research run is still in progress when primary-path retrieval is already proven against a completed live session.

Acceptance status:

- `PASS`: primary-path canonical retrieval proven on live runtime
- `PASS`: provisional guard behavior still present on a fresh live run
- `PASS`: targeted regression suites green

## 5. Targeted test evidence

The following targeted suites were run green in this corrective wave:

1. [tests/test_agent_mcp.py](/vol1/1000/projects/ChatgptREST/tests/test_agent_mcp.py)
2. [tests/test_mcp_server_entrypoints.py](/vol1/1000/projects/ChatgptREST/tests/test_mcp_server_entrypoints.py)
3. [tests/test_agent_v3_route_work_sample_validation.py](/vol1/1000/projects/ChatgptREST/tests/test_agent_v3_route_work_sample_validation.py)

Combined rerun:

- `55 passed`

## 6. What is now production-ready

For the current narrow coding-agent lane, the following statement is now defensible:

> `coding-agent-v1` is production-ready as the default public coding-agent surface for ChatgptREST, with explicit degraded fallback semantics and live observability.

That statement is limited to:

1. public MCP ingress
2. session/status/answer contract
3. jobs-answer primary path
4. timer-backed planning-review maintenance installation
5. route-validation regression stability

## 7. What this completion does not claim

This wave does **not** claim:

1. broad platform simplification is complete
2. `scope_project` live backfill is approved
3. promotion throughput has been solved
4. `advisor_agent_*` is retired
5. every fresh Deep Research run will always complete inside a short deterministic wall-clock window

Those remain outside the scope of V5 completion.
