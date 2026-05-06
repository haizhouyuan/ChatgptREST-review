# Next-Stage Execution TODO Master V4

Date: 2026-04-08

Supersedes:

- [Next-Stage Execution TODO Master V3](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-04-08_next_stage_execution_todo_master_v3.md)

## Current program state

Completed:

- Work Package 0 preflight evidence pack
- Work Package B coding-agent-v1 default contract
- Work Package C OpenClaw entry-policy contract

Authoritative outputs added in this step:

- [OpenClaw Entry-Policy Contract Implementation V1](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-08_openclaw_entry_policy_contract_implementation_v1.md)
- [OpenClaw Entry-Policy Contract Walkthrough V1](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-04-08_openclaw_entry_policy_contract_walkthrough_v1.md)

## Remaining checklist

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

1. Entry-policy runtime provenance is now explicit at the plugin boundary; later gates should consume `details.entry_policy` rather than re-infer it.
2. Ambiguous mixed-project traffic now fails closed locally; later work should not undo this by reintroducing silent fallback.
3. `status` is now a read path, not necessarily a new turn; later docs and gates must preserve that distinction.
