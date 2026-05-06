# Next-Stage Execution TODO Master V16

Date: 2026-04-08

Supersedes:

- [Next-Stage Execution TODO Master V15](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-04-08_next_stage_execution_todo_master_v15.md)

Program anchor:

- [Refined Next-Stage Full Execution Plan V5](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-08_refined_next_stage_full_execution_plan_v5.md)

## Active wave: productionization corrective wave

### Q. jobs-answer primary-path repair

- [ ] Q1. split public-agent auth helper from jobs bearer helper
- [ ] Q2. route `_job_answer` through jobs bearer auth only
- [ ] Q3. add/update tests for primary-path bearer usage and degraded fallback
- [ ] Q4. verify live runtime can return `source=job_answer_api`

### R. public MCP observability completion

- [ ] R1. add public MCP `/health` custom route
- [ ] R2. expose primary-path vs degraded-path readiness without leaking secrets
- [ ] R3. add MCP health test
- [ ] R4. verify live `curl http://127.0.0.1:18712/health`

### S. promotion maintenance scheduler recovery

- [ ] S1. install reviewed planning-review maintenance unit in live user systemd runtime
- [ ] S2. enable and start the timer
- [ ] S3. capture installed/scheduled evidence
- [ ] S4. capture at least one fresh maintenance run artifact

### T. route-validation suite correction

- [ ] T1. inspect the failing workforce-planning sample
- [ ] T2. apply the narrow correction to behavior or dataset
- [ ] T3. re-run `tests/test_agent_v3_route_work_sample_validation.py`

### U. live production-readiness revalidation

- [ ] U1. re-run the live Deep Research finality gate
- [ ] U2. verify whether live answer retrieval is `job_answer_api` or degraded fallback
- [ ] U3. run targeted MCP tests and touched regression tests
- [ ] U4. write productionization completion summary and residual risk note

## Carry-forward constraints

- `coding_agent_*` remains the default mature coding-agent lane
- `advisor_agent_*` remains the broad advisor / compatibility lane
- `scope_project` live broad backfill remains blocked
- promotion threshold tuning remains blocked until post-scheduler evidence exists
