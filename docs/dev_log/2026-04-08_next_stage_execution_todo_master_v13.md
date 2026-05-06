# Next-Stage Execution TODO Master V13

Date: 2026-04-08

Supersedes:

- [Next-Stage Execution TODO Master V12](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-04-08_next_stage_execution_todo_master_v12.md)

## Completed program anchor

The boundary-consolidation release remains completed.

V13 records two additional follow-on deliverables as completed:

- the `scope_project` live-backfill readiness decision
- the promotion low-active root-cause diagnosis

## Active follow-on wave

Reference plan:

- [Refined Next-Stage Full Execution Plan V3](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-08_refined_next_stage_full_execution_plan_v3.md)
- [Public Lane Lifecycle Decision V1](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-08_public_lane_lifecycle_decision_v1.md)
- [Scope Project Live Backfill Readiness Decision V1](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-08_scope_project_live_backfill_readiness_decision_v1.md)
- [Promotion Low-Active Root-Cause Diagnosis V1](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-08_promotion_low_active_root_cause_diagnosis_v1.md)

### G. Public-lane lifecycle decision

- [x] G1. write one explicit lane-governance decision record
- [x] G2. update `AGENTS.md` / wrapper docs with the frozen lane relationship
- [x] G3. verify no maintained doc still describes both `advisor_agent_*` and `coding_agent_*` as coding-agent defaults

### H. Live Deep Research finality gate

- [x] H1. define the live gate scope and supported provider lane
- [x] H2. implement runner and artifact layout
- [x] H2a. remove duplicate-guard false failures by preserving narrow-lane structured errors and adding a unique run tag
- [ ] H3. prove provisional does not present as final in a completed live evidence pack
- [ ] H4. prove final canonical retrieval path works through the supported public lane
- [ ] H5. write review packet and commit the completed gate

### I. `scope_project` live-backfill precondition pack

- [x] I1. rerun current scope-project audit
- [x] I2. compare mismatch/orphan/noisy-project results against old preflight evidence
- [x] I3. write explicit readiness decision: safe / conditional / blocked
- [x] I4. decide whether live backfill is approved or deferred

Decision frozen in V13:

- live backfill remains `deferred`
- any future write requires mismatch-family adjudication and a narrowed dry-run approval pack

### J. Promotion root-cause diagnosis

- [x] J1. collect current promotion evidence bundle
- [x] J2. identify dominant low-active cause with evidence
- [x] J3. write diagnosis packet
- [x] J4. state which follow-on actions are justified and which are not yet justified

Decision frozen in V13:

- dominant failure mode is `scheduling_absence`
- threshold tuning is not justified until scheduling is restored and observed

## Carry-forward constraints

- keep `coding_agent_*` as the default mature coding-agent lane unless a new explicit decision supersedes it
- keep `advisor_agent_*` available as the broad public advisor / compatibility lane unless an explicit deprecation plan supersedes this decision
- do not run live `scope_project` backfill just because the script exists
- do not treat the current green unified gate pack as a substitute for a live Deep Research finality proof
- do not treat promotion inventory + maintenance as equivalent to solved promotion throughput
- do not claim promotion gate thresholds are the main bottleneck until maintenance scheduling is restored and observed advancing
