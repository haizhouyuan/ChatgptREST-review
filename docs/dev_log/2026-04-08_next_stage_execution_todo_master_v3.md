# Next-Stage Execution TODO Master V3

Date: 2026-04-08

Supersedes:

- [Next-Stage Execution TODO Master V2](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-04-08_next_stage_execution_todo_master_v2.md)

## Purpose

This is the live execution anchor after completing Work Package B.

It exists so the remaining work can resume cleanly even if context is compressed.

## Current program state

Completed:

- Work Package 0 preflight evidence pack
- Work Package B coding-agent-v1 default contract

Authoritative outputs:

- [Refined Next-Stage Full Execution Plan V2](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-08_refined_next_stage_full_execution_plan_v2.md)
- [Next-Stage Preflight Evidence Pack V1](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-08_next_stage_preflight_evidence_pack_v1.md)
- [Coding-Agent-V1 Default Contract Implementation V1](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-08_coding_agent_v1_default_contract_implementation_v1.md)
- [Coding-Agent-V1 Default Contract Walkthrough V1](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-04-08_coding_agent_v1_default_contract_walkthrough_v1.md)

## Master checklist

### A. Preflight evidence pack

- [x] A1. scope_project data audit
- [x] A2. promotion pipeline diagnosis
- [x] A3. authority-doc integrity scan
- [x] A4. project-scoped retrieval baseline/replay set
- [x] A5. auxiliary read-only documents-table audit
- [x] A6. auxiliary read-only planning runtime pack audit
- [x] A7. write preflight evidence summary document
- [x] A8. commit preflight evidence outputs

### B. Coding-agent-v1 default contract

- [x] B1. inspect current public MCP / routes / wrappers against V2 contract
- [x] B2. define the concrete implementation shape for coding-agent-v1
- [x] B3. implement the narrow request contract
- [x] B4. implement the narrow response/finality contract
- [x] B5. align wrappers and default docs/examples
- [x] B6. add acceptance tests for long/provisional/no-job/short-answer flows
- [x] B7. write walkthrough and commit

### C. OpenClaw entry-policy contract

- [ ] C1. inspect current OpenClaw/OpenMind routing behavior against V2 contract
- [ ] C2. define explicit `project_id / association_source / task_mode` contract
- [ ] C3. implement rules-first project association
- [ ] C4. implement conservative `continue / branch / status / clarify` behavior
- [ ] C5. prevent fallback into local ad hoc handling where routing should occur
- [ ] C6. add replay/acceptance coverage
- [ ] C7. write walkthrough and commit

### D. Structural authority governance

- [ ] D1. inspect current authority anchor/runtime injection path
- [ ] D2. define and/or tighten authority anchor schema
- [ ] D3. add first-class authority source handling in runtime assembly
- [ ] D4. implement context preview / conflict visibility / stale detection
- [ ] D5. wire authority-doc integrity checks into governance flow
- [ ] D6. add conflict and trimming acceptance coverage
- [ ] D7. write walkthrough and commit

### E. Unified release gate pack

- [ ] E1. define the single gate-pack manifest/runner shape
- [ ] E2. wire coding-agent lane gate
- [ ] E3. wire OpenClaw entry gate
- [ ] E4. wire authority precedence gate
- [ ] E5. wire promotion-maintenance safety gate
- [ ] E6. run the full gate pack
- [ ] E7. write release evidence summary and commit

### F. Final reflection and closeout

- [ ] F1. compare achieved state vs intended end-state
- [ ] F2. write final implementation summary
- [ ] F3. write residual gap/risk note if anything remains
- [ ] F4. run scoped closeout

## Hard findings carried forward

1. `scope_project` write-back remains conditional because live mismatches and orphan atoms exist.
2. promotion’s dominant current blocker is missing/absent maintenance scheduling, not yet proven gate strictness.
3. authority anchors are structurally healthy and can now move into governance hardening.
4. the project-scoped retrieval baseline is real and reusable.
5. coding-agent defaults are now frozen to the narrow public MCP lane; further work should not reopen the broad advisor default.

## Execution rule from this point

Do not reopen Work Package B unless:

- a later work package invalidates the coding-agent-v1 contract, or
- the unified gate pack fails against the B acceptance cases.
