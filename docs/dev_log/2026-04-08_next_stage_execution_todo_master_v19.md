# Next-Stage Execution TODO Master V19

Date: 2026-04-08

Supersedes:

- [Next-Stage Execution TODO Master V18](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-04-08_next_stage_execution_todo_master_v18.md)

Program anchor:

- [Refined Next-Stage Full Execution Plan V6](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-08_refined_next_stage_full_execution_plan_v6.md)

Completion anchor:

- [V6 Production-Grade Completion Summary V1](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-08_v6_production_grade_completion_summary_v1.md)

## V6 completion state

### A. Wrapper surface auto-selection hardening

- [x] A1. add resolved surface selection logic before preflight validation
- [x] A2. auto-route advisor-only argument sets to `advisor-agent`
- [x] A3. preserve `coding-agent-v1` default for narrow requests
- [x] A4. fix recovery hints so they reference the resolved lane
- [x] A5. re-run `tests/test_skill_chatgptrest_call.py`

### B. Planning bulk scoring and promotion pipeline

- [x] B1. design a planning-only bulk runner with dry-run/live separation
- [x] B2. update groundedness in bounded batches without mutating generic checker semantics
- [x] B3. promote anchored planning atoms to `active`
- [x] B4. promote non-anchored but eligible planning atoms to `candidate`
- [x] B5. capture monitor artifacts and promotion/groundedness deltas

### C. Dedicated promotion scheduler installation

- [x] C1. add service/timer pair for the new planning bulk runner
- [x] C2. install the unit pair into live user systemd
- [x] C3. enable the timer and capture scheduled-state evidence
- [x] C4. capture at least one live scheduler run

### D. Planning runtime-pack refresh

- [x] D1. refresh the reviewed planning runtime pack after the bulk cycle
- [x] D2. capture growth/freshness evidence
- [x] D3. document whether allowlist boundaries still cap pack breadth

### E. KB hybrid runtime hardening

- [x] E1. prove the live service runtime uses `.venv`
- [x] E2. prove `fastembed` is importable in that runtime
- [x] E3. capture FTS/vector coverage counts
- [x] E4. capture a vector-enabled hybrid smoke query

### F. Regression and final acceptance

- [x] F1. re-run wrapper + planning-plane regression slice under `.venv`
- [x] F2. fix any V6-touched regressions
- [x] F3. capture public MCP `/health`
- [x] F4. capture planning explicit-pack primary-path proof
- [x] F5. write V6 completion summary, residual risk note, and walkthrough
- [ ] F6. run repo closeout

## Deferred after V6

- [ ] repo-wide full-suite re-baseline
- [ ] broad `scope_project` live backfill approval
- [ ] global non-planning promotion scheduler beyond the V6 planning lane
