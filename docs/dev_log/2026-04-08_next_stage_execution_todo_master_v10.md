# Next-Stage Execution TODO Master V10

Date: 2026-04-08

Supersedes:

- [Next-Stage Execution TODO Master V9](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-04-08_next_stage_execution_todo_master_v9.md)

## Completed program anchor

The boundary-consolidation release remains completed.

What changes in V10 is not the completion status of that program, but the explicit definition of the **next** follow-on wave.

## Next follow-on wave

Reference plan:

- [Refined Next-Stage Full Execution Plan V3](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-08_refined_next_stage_full_execution_plan_v3.md)

### G. Public-lane lifecycle decision

- [ ] G1. write one explicit lane-governance decision record
- [ ] G2. update `AGENTS.md` / wrapper docs with the frozen lane relationship
- [ ] G3. verify no maintained doc still describes both `advisor_agent_*` and `coding_agent_*` as coding-agent defaults

### H. Live Deep Research finality gate

- [ ] H1. define the live gate scope and supported provider lane
- [ ] H2. implement runner and artifact layout
- [ ] H3. prove provisional does not present as final
- [ ] H4. prove final canonical retrieval path works through the supported public lane
- [ ] H5. write review packet and commit

### I. `scope_project` live-backfill precondition pack

- [ ] I1. rerun current scope-project audit
- [ ] I2. compare mismatch/orphan/noisy-project results against old preflight evidence
- [ ] I3. write explicit readiness decision: safe / conditional / blocked
- [ ] I4. decide whether live backfill is approved or deferred

### J. Promotion root-cause diagnosis

- [ ] J1. collect current promotion evidence bundle
- [ ] J2. identify dominant low-active cause with evidence
- [ ] J3. write diagnosis packet
- [ ] J4. state which follow-on actions are justified and which are not yet justified

## Carry-forward constraints

- keep `coding_agent_*` as the default mature coding-agent lane unless a new explicit decision supersedes it
- do not run live `scope_project` backfill just because the script exists
- do not treat the current green unified gate pack as a substitute for a live Deep Research finality proof
- do not treat promotion inventory + maintenance as equivalent to solved promotion throughput
