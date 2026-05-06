# A To F Execution And Harness Summary V1

Date: 2026-04-07

## Scope

This document closes the `A-F` implementation run for:

- public agent MCP completion-contract repair
- controller completion-contract reconcile
- EvoMap `scope_project` groundwork
- project-scoped substrate threading
- OpenMind plugin project propagation
- promotion inventory + planning review maintenance harness

## Commit sequence

ChatgptREST commits:

1. `97a3b5fb` `Add full execution master plan for A-F rollout`
2. `8efc5d52` `Project completion contract to public agent MCP`
3. `ca82c3d1` `Make controller reconcile completion-contract aware`
4. `fa7f585f` `Add EvoMap scope project groundwork`
5. `f03f2cd0` `Thread project scope through advisor context hot path`
6. `5e377a51` `Propagate project scope through OpenMind plugins`
7. `f7003e82` `Add promotion inventory and maintenance harness`

Planning repo commit:

- `8de8fea2` `Add PRS project context authority anchor`

## Workstream summary

### A. Public agent MCP completion contract

Closed in:

- `8efc5d52`
- `ca82c3d1`

Effect:

- public agent surface now projects completion-contract semantics
- coding-agent wrapper no longer depends on `last_answer` as the only answer source
- controller reconcile is contract-aware

Supporting docs:

- [public agent MCP walkthrough](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-04-07_public_agent_mcp_completion_contract_projection_walkthrough_v1.md)
- [public agent MCP review packet](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-07_public_agent_mcp_completion_contract_projection_review_packet_for_claude_v1.md)
- [controller reconcile walkthrough](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-04-07_controller_completion_contract_reconcile_walkthrough_v1.md)
- [controller reconcile review packet](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-07_controller_completion_contract_reconcile_review_packet_for_claude_v1.md)

### B. EvoMap scope project groundwork

Closed in:

- `fa7f585f`

Effect:

- `Atom.scope_project` and DB/runtime schema aligned
- backfill script added and executed
- ingest mirror now writes `scope_project`

Supporting docs:

- [scope groundwork walkthrough](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-04-07_evomap_scope_project_groundwork_walkthrough_v1.md)
- [scope groundwork review packet](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-07_evomap_scope_project_groundwork_review_packet_for_claude_v1.md)

### C + D. Project scope threading and authority contract

Closed in:

- `f03f2cd0`

Effect:

- `project_id` threaded through memory/context/retrieval hot path
- authority anchor is explicitly prioritized over project memory / EvoMap knowledge / heuristics
- planning ingress writes project-scoped work memory

Supporting docs:

- [project scope threading walkthrough](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-04-07_project_scope_threading_and_authority_priority_walkthrough_v1.md)
- [project scope threading review packet](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-07_project_scope_threading_and_authority_priority_review_packet_for_claude_v1.md)

### E. OpenMind plugin project propagation

Closed in:

- `5e377a51`
- planning repo `8de8fea2`

Effect:

- `openmind-advisor`, `openmind-memory`, `openmind-telemetry` now propagate `project_id`
- project-aware recall/capture/telemetry works through OpenClaw plugins
- PRS authority anchor added

Supporting docs:

- [plugin propagation walkthrough](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-04-07_openmind_plugins_project_scope_propagation_walkthrough_v1.md)
- [plugin propagation review packet](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-07_openmind_plugins_project_scope_propagation_review_packet_for_claude_v1.md)

### F. Promotion inventory and maintenance harness

Closed in:

- `f7003e82`

Effect:

- generic promotion inventory report added
- planning review maintenance harness added
- refresh-only timer template added
- no generic auto-promotion introduced

Supporting docs:

- [F walkthrough](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-04-07_evomap_promotion_inventory_and_maintenance_harness_walkthrough_v1.md)
- [F review packet](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-07_evomap_promotion_inventory_and_maintenance_harness_review_packet_for_claude_v1.md)

## Harness evidence

Live inventory artifacts:

- [promotion inventory json](/vol1/1000/projects/ChatgptREST/artifacts/monitor/evomap/promotion_inventory_20260407_fline/promotion_inventory_20260407T120552Z.json)
- [promotion blockers markdown](/vol1/1000/projects/ChatgptREST/artifacts/monitor/evomap/promotion_inventory_20260407_fline/promotion_blockers_20260407T120552Z.md)

Live maintenance harness artifacts:

- [maintenance summary](/vol1/1000/projects/ChatgptREST/artifacts/monitor/planning_review_maintenance_20260407_fline/20260407T120524Z/summary.json)
- [maintenance readme](/vol1/1000/projects/ChatgptREST/artifacts/monitor/planning_review_maintenance_20260407_fline/20260407T120524Z/README.md)
- [cycle payload](/vol1/1000/projects/ChatgptREST/artifacts/monitor/planning_review_maintenance_20260407_fline/20260407T120524Z/cycle_payload.json)

## Validation

Per-batch targeted validation was run during each commit.

Final combined A-F regression:

```bash
./.venv/bin/pytest -q \
  tests/test_agent_mcp.py \
  tests/test_job_view_progress_fields.py \
  tests/test_contract_v1.py \
  tests/test_cognitive_api.py \
  tests/test_openclaw_cognitive_plugins.py \
  tests/test_capture_work_memory.py \
  tests/test_advisor_runtime.py \
  tests/test_evomap_scope_project.py \
  tests/test_context_service_work_memory.py \
  tests/test_task_intake.py \
  tests/test_prompt_builder.py \
  tests/test_work_memory_manager.py \
  tests/test_routes_agent_v3_planning_project_scope.py \
  tests/test_report_evomap_promotion_inventory.py \
  tests/test_run_planning_review_maintenance.py
```

Result: passed.

## External review status

I attempted to use the user-provided resumed `claudegac` session for review. Resume/fork worked, but the mirror returned:

- `API Error: 402 {"error":"Insufficient credits"}`

So the final state is:

- implementation complete
- tests green
- harness artifacts present
- external GAC review attempted but blocked by credits

## Intentional non-goals

This run did **not**:

- replace advisor-agent product boundaries wholesale
- introduce generic auto-promotion for staged atoms
- change the reviewed planning bootstrap algorithm
- touch unrelated dirty files already present in the repo
