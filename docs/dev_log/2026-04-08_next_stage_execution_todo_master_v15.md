# Next-Stage Execution TODO Master V15

Date: 2026-04-08

Supersedes:

- [Next-Stage Execution TODO Master V14](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-04-08_next_stage_execution_todo_master_v14.md)

## Program anchor

The red-team follow-on wave is complete.

V15 starts the next root-fix wave described in:

- [Refined Next-Stage Full Execution Plan V4](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-08_refined_next_stage_full_execution_plan_v4.md)

## Active wave: systemic coherence hardening

### K. Auth-domain separation and primary-path repair

- [ ] K1. split public-agent auth helpers from jobs bearer helpers
- [ ] K2. update internal HTTP helpers to use the correct token domain
- [ ] K3. add startup or self-check evidence for degraded vs primary-path runtime
- [ ] K4. document the correct service env contract

### L. Public-surface governance completion

- [ ] L1. freeze one machine-checkable lane policy source
- [ ] L2. make default / compatibility / future deprecation status explicit in docs and wrappers
- [ ] L3. add a gate that fails on lane-policy drift

### M. Live gate hardening

- [ ] M1. distinguish primary-path green from degraded-path green
- [ ] M2. add auth-domain smoke coverage to the live gate set
- [ ] M3. add maintenance-presence checks where policy requires them

### N. `scope_project` adjudication path

- [ ] N1. write mismatch-family adjudication note
- [ ] N2. freeze canonical project-namespace rules
- [ ] N3. produce narrowed dry-run candidate report
- [ ] N4. keep live write blocked until reviewed dry-run approval exists

### O. Promotion maintenance recovery

- [ ] O1. install or enable the reviewed maintenance unit in the live runtime
- [ ] O2. capture evidence that the scheduler is running
- [ ] O3. rerun promotion inventory after maintenance advances
- [ ] O4. decide whether any throughput tuning is justified after that evidence

### P. Authority/runtime governance completion

- [ ] P1. add required-field / ownership / stale-handling governance for authority anchors
- [ ] P2. gate missing or structurally invalid authority material
- [ ] P3. verify runtime truth never outranks authority anchor

## Carry-forward constraints

- `coding_agent_*` remains the default mature coding-agent lane
- `advisor_agent_*` remains the broad advisor / compatibility lane
- `last_answer_fallback` remains allowed, but must be treated as degraded mode rather than the target primary path
- no live `scope_project` backfill is approved yet
- no promotion threshold tuning is approved until maintenance scheduling is live and evidenced
