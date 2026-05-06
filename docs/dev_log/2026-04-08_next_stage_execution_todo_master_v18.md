# Next-Stage Execution TODO Master V18

Date: 2026-04-08

Supersedes:

- [Next-Stage Execution TODO Master V17](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-04-08_next_stage_execution_todo_master_v17.md)

Program anchor:

- [Refined Next-Stage Full Execution Plan V6](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-08_refined_next_stage_full_execution_plan_v6.md)

## V6 production-grade platform hardening

### A. Wrapper surface auto-selection hardening

- [ ] A1. add resolved surface selection logic before preflight validation
- [ ] A2. auto-route advisor-only argument sets to `advisor-agent`
- [ ] A3. preserve `coding-agent-v1` default for narrow requests
- [ ] A4. fix recovery hints so they reference the resolved lane
- [ ] A5. re-run `tests/test_skill_chatgptrest_call.py`

### B. Planning bulk scoring and promotion pipeline

- [ ] B1. design a planning-only bulk runner with dry-run/live separation
- [ ] B2. update groundedness in bounded batches without mutating generic checker semantics
- [ ] B3. promote anchored planning atoms to `active`
- [ ] B4. promote non-anchored but eligible planning atoms to `candidate`
- [ ] B5. capture monitor artifacts and promotion/groundedness deltas

### C. Dedicated promotion scheduler installation

- [ ] C1. add service/timer pair for the new planning bulk runner
- [ ] C2. install the unit pair into live user systemd
- [ ] C3. enable the timer and capture scheduled-state evidence
- [ ] C4. capture at least one live scheduler run

### D. Planning runtime-pack refresh

- [ ] D1. refresh the reviewed planning runtime pack after the bulk cycle
- [ ] D2. capture growth/freshness evidence
- [ ] D3. document whether allowlist boundaries still cap pack breadth

### E. KB hybrid runtime hardening

- [ ] E1. prove the live service runtime uses `.venv`
- [ ] E2. prove `fastembed` is importable in that runtime
- [ ] E3. capture FTS/vector coverage counts
- [ ] E4. capture a vector-enabled hybrid smoke query

### F. Regression and final acceptance

- [ ] F1. re-run wrapper + planning-plane regression slice under `.venv`
- [ ] F2. fix any V6-touched regressions
- [ ] F3. capture public MCP `/health`
- [ ] F4. capture coding-agent primary-path answer proof
- [ ] F5. write V6 completion summary, residual risk note, and walkthrough
- [ ] F6. run repo closeout
