# Next-Stage Execution TODO Master V17

Date: 2026-04-08

Supersedes:

- [Next-Stage Execution TODO Master V16](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-04-08_next_stage_execution_todo_master_v16.md)

Program anchor:

- [Refined Next-Stage Full Execution Plan V5](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-08_refined_next_stage_full_execution_plan_v5.md)

Completion record:

- [Productionization Corrective Wave Completion V1](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-08_productionization_corrective_wave_completion_v1.md)

## Productionization corrective wave status

### Q. jobs-answer primary-path repair

- [x] Q1. split public-agent auth helper from jobs bearer helper
- [x] Q2. route `_job_answer` through jobs bearer auth only
- [x] Q3. add/update tests for primary-path bearer usage and degraded fallback
- [x] Q4. verify live runtime can return `source=job_answer_api`
- [x] Q5. fix the newly discovered chunk-contract parser mismatch in `_job_answer`

### R. public MCP observability completion

- [x] R1. add public MCP `/health` custom route
- [x] R2. expose primary-path vs degraded-path readiness without leaking secrets
- [x] R3. add MCP health test
- [x] R4. verify live `curl http://127.0.0.1:18712/health`

### S. promotion maintenance scheduler recovery

- [x] S1. install reviewed planning-review maintenance unit in live user systemd runtime
- [x] S2. enable and start the timer
- [x] S3. capture installed/scheduled evidence
- [x] S4. capture at least one fresh maintenance run artifact

### T. route-validation suite correction

- [x] T1. inspect the failing workforce-planning sample
- [x] T2. apply the narrow correction to behavior or dataset
- [x] T3. re-run `tests/test_agent_v3_route_work_sample_validation.py`

### U. live production-readiness revalidation

- [x] U1. re-run targeted live validation after Q-R-S-T
- [x] U2. prove primary-path retrieval on live runtime using a completed deep-research session
- [x] U3. confirm provisional guard behavior on a fresh live deep-research run
- [x] U4. run targeted MCP and route-validation regression suites
- [x] U5. write completion summary and residual risk note

## Final reading

The V5 wave is complete for the current `coding-agent-v1` lane.

Carry-forward constraints remain:

- `coding_agent_*` remains the default mature coding-agent lane
- `advisor_agent_*` remains the broad advisor / compatibility lane
- `scope_project` live broad backfill remains blocked
- promotion throughput tuning remains blocked until a later post-scheduler evidence wave
