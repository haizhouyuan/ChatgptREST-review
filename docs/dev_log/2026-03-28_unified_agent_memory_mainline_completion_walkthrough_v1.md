# 2026-03-28 Unified Agent Memory Mainline Completion Walkthrough v1

## Scope

This pass focused on the remaining mainline blockers for the unified agent memory system inside ChatgptREST:

- planning runtime pack on the default `/v2/context/resolve` knowledge path
- first-class memory identity columns in `memory.db`
- `context/resolve` and `memory.capture` read/write paths using first-class identity columns
- graph family router and explainability metadata on `/v2/graph/query`
- runtime wiring evidence for skill platform registry / market gate components

## What Changed

### 1. Memory identity became first-class in `memory.db`

Updated [memory_manager.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/memory_manager.py) to:

- add first-class `session_id`, `agent_id`, `role_id`, `account_id`, `thread_id` columns
- backfill those columns from legacy `source` JSON on startup migration
- re-backfill blank rows even if the columns already exist
- write the first-class columns on insert and on dedup-update merge
- swap episodic / semantic / working read paths from `json_extract(source, ...)` to direct column filters
- add identity-oriented indexes for `session`, `agent+role`, `account+thread`, and dedup scope

Validation lives in [test_memory_tenant_isolation.py](/vol1/1000/projects/ChatgptREST/tests/test_memory_tenant_isolation.py).

### 2. Planning runtime pack is now part of the default context-resolve knowledge chain

Updated [context_service.py](/vol1/1000/projects/ChatgptREST/chatgptrest/cognitive/context_service.py) so that:

- approved planning runtime pack hits are searched on the default knowledge path when knowledge retrieval is enabled
- planning pack hits show up as a dedicated `planning_pack` context block with provenance
- the resolved prompt prefix now includes a `## Planning Runtime Pack` section
- resolve metadata records `planning_pack_hits`
- retrieval-plan explainability distinguishes pack hits from ordinary KB hits

Validation lives in [test_cognitive_api.py](/vol1/1000/projects/ChatgptREST/tests/test_cognitive_api.py).

### 3. Graph family router / explainability was hardened

Updated [graph_service.py](/vol1/1000/projects/ChatgptREST/chatgptrest/cognitive/graph_service.py) and [routes_cognitive.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_cognitive.py) to:

- normalize legacy scopes (`personal_graph`, `repo_graph`) into graph families (`business`, `repo_code`, `issue_execution`)
- keep legacy callers compatible
- restore `promotion_status_counts` in response metadata for existing callers
- add `family_router` explainability metadata with alias mapping and degradation notes
- keep `promotion_audit` metadata for graph explainability

Validation lives in [test_cognitive_api.py](/vol1/1000/projects/ChatgptREST/tests/test_cognitive_api.py).

### 4. Skill platform runtime components are real runtime resources

Updated [runtime.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/runtime.py) so `capability_gap_recorder` is closed during runtime reset, matching the newly wired:

- `skill_registry`
- `bundle_resolver`
- `capability_gap_recorder`
- `quarantine_gate`

Validation lives in [test_advisor_runtime.py](/vol1/1000/projects/ChatgptREST/tests/test_advisor_runtime.py).

## Tests

Executed:

```bash
PYTHONPATH=. ./.venv/bin/pytest -q \
  tests/test_cognitive_api.py \
  tests/test_memory_tenant_isolation.py \
  tests/test_planning_runtime_pack_search.py \
  tests/test_advisor_runtime.py \
  tests/test_skill_manager.py \
  tests/test_market_gate.py \
  tests/test_controller_engine_planning_pack.py
```

Result: pass.

## Remaining Gaps

- `issue_execution` is still an adapter seam with `NullIssueGraphAdapter` as the default. The router and explainability path now exist, but the live issue graph backend is still not enabled in this pass.
- planning-side acceptance and close/open topic status still need to be synchronized in `/vol1/1000/projects/planning`.
