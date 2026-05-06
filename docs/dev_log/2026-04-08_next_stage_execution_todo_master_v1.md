# Next-Stage Execution TODO Master V1

Date: 2026-04-08

## Purpose

This document is the execution anchor for implementing:

- [Refined Next-Stage Full Execution Plan V2](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-08_refined_next_stage_full_execution_plan_v2.md)

Its purpose is to prevent context loss during a long implementation cycle.

If execution context is compressed, resumed, or handed over, this file is the first operational document to read.

## Execution mode decision

Primary implementation mode for this program:

- main development is owned by Codex in this repo

`claudeminmax` usage policy:

- not used by default for the main implementation path
- may be used only for bounded side analysis or second-opinion review when:
  - the subtask is read-only or low-write-risk
  - the output does not create merge ambiguity
  - the subtask is not on the critical path of a tightly coupled code change

Reason:

- the core implementation path spans coupled contract/runtime/eval surfaces
- consistency is more important than parallel code-writing throughput

## Master objective

Finish the next-stage consolidation release so that:

1. coding agents have a narrow, stable default contract
2. OpenClaw behaves as an entry-layer orchestrator rather than a hidden project brain
3. authority precedence is structural and inspectable
4. release gating is unified and machine-verifiable

## Master checklist

### A. Preflight evidence pack

- [ ] A1. scope_project data audit
- [ ] A2. promotion pipeline diagnosis
- [ ] A3. authority-doc integrity scan
- [ ] A4. project-scoped retrieval baseline/replay set
- [ ] A5. auxiliary read-only documents-table audit
- [ ] A6. auxiliary read-only planning runtime pack audit
- [ ] A7. write preflight evidence summary document
- [ ] A8. commit preflight evidence outputs

### B. Coding-agent-v1 default contract

- [ ] B1. inspect current public MCP / routes / wrappers against V2 contract
- [ ] B2. define the concrete implementation shape for coding-agent-v1
- [ ] B3. implement the narrow request contract
- [ ] B4. implement the narrow response/finality contract
- [ ] B5. align wrappers and default docs/examples
- [ ] B6. add acceptance tests for long/provisional/no-job/short-answer flows
- [ ] B7. write walkthrough and commit

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

## Guardrails

### Do not do

- do not expand this stage into broad promotion throughput optimization
- do not build a new standalone project-context subsystem
- do not reopen advisor-heavy defaults for coding agents
- do not let auxiliary audits turn into cleanup execution without explicit new scope

### Must preserve

- one meaningful change => one commit
- each doc version stays as a new file
- unrelated dirty worktree changes are not touched
- full validation and release evidence must be recorded before claiming success

## Required anchor documents

Read these before resuming work:

- [Refined Next-Stage Full Execution Plan V2](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-08_refined_next_stage_full_execution_plan_v2.md)
- [Dual-Model External Review Synthesis And Platform Decision V1](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-07_dual_model_external_review_synthesis_and_platform_decision_v1.md)
- [Dual-Model External Review Execution And Findings V1](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-04-07_dual_model_external_review_execution_and_findings_v1.md)
- [Next-Stage TODO And Memory Guard V1](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-04-07_next_stage_todo_and_memory_guard_v1.md)

## Completion rule

Do not report completion to the user until:

- every checklist block above is either done or explicitly written into a residual-risk note
- the gate pack has been run
- the final reflection has been written
- closeout has succeeded
