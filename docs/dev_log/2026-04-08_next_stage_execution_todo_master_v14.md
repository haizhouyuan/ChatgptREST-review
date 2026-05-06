# Next-Stage Execution TODO Master V14

Date: 2026-04-08

Supersedes:

- [Next-Stage Execution TODO Master V13](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-04-08_next_stage_execution_todo_master_v13.md)

## Completed program anchor

The boundary-consolidation release remains completed.

V14 marks the entire red-team follow-on wave as complete:

- G. public-lane lifecycle decision
- H. live Deep Research finality gate
- I. `scope_project` live-backfill readiness decision
- J. promotion low-active root-cause diagnosis

## Final status of the follow-on wave

### G. Public-lane lifecycle decision

- [x] G1. write one explicit lane-governance decision record
- [x] G2. update `AGENTS.md` / wrapper docs with the frozen lane relationship
- [x] G3. verify no maintained doc still describes both `advisor_agent_*` and `coding_agent_*` as coding-agent defaults

### H. Live Deep Research finality gate

- [x] H1. define the live gate scope and supported provider lane
- [x] H2. implement runner and artifact layout
- [x] H2a. remove duplicate-guard false failures by preserving narrow-lane structured errors and adding a unique run tag
- [x] H3. prove provisional does not present as final in a completed live evidence pack
- [x] H4. prove final canonical retrieval path works through the supported public lane
- [x] H5. write review packet and commit the completed gate

Frozen completion artifact:

- [Live Deep Research Finality Gate Completion V1](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-08_live_deep_research_finality_gate_completion_v1.md)

### I. `scope_project` live-backfill precondition pack

- [x] I1. rerun current scope-project audit
- [x] I2. compare mismatch/orphan/noisy-project results against old preflight evidence
- [x] I3. write explicit readiness decision: safe / conditional / blocked
- [x] I4. decide whether live backfill is approved or deferred

Frozen decision:

- live backfill remains `deferred`

### J. Promotion root-cause diagnosis

- [x] J1. collect current promotion evidence bundle
- [x] J2. identify dominant low-active cause with evidence
- [x] J3. write diagnosis packet
- [x] J4. state which follow-on actions are justified and which are not yet justified

Frozen decision:

- dominant failure mode remains `scheduling_absence`

## Carry-forward constraints

- keep `coding_agent_*` as the default mature coding-agent lane unless a new explicit decision supersedes it
- keep `advisor_agent_*` available as the broad public advisor / compatibility lane unless an explicit deprecation plan supersedes this decision
- do not run live `scope_project` backfill just because the script exists
- do not treat promotion inventory + maintenance as equivalent to solved promotion throughput
- do not treat the green live Deep Research gate as proof that the internal jobs answer API is now universally readable from the public MCP runtime; the supported contract is the successful public answer surface, including safe session fallback when required
