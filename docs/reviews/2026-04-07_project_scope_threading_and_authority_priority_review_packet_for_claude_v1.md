# 2026-04-07 Project Scope Threading And Authority Priority Review Packet For Claude v1

## Review Goal

Review the C+D substrate batch that introduces `project_id` threading across memory/context retrieval and enforces authority-anchor priority in advisor prompt assembly.

## Scope

### Included

- `chatgptrest/api/routes_agent_v3.py`
- `chatgptrest/kernel/memory_manager.py`
- `chatgptrest/kernel/work_memory_manager.py`
- `chatgptrest/cognitive/context_service.py`
- `chatgptrest/kernel/context_assembler.py`
- `chatgptrest/api/routes_cognitive.py`
- `chatgptrest/evomap/knowledge/retrieval.py`
- `chatgptrest/advisor/task_intake.py`
- `chatgptrest/advisor/prompt_builder.py`
- targeted regression tests

### Explicitly excluded

- OpenClaw/OpenMind runtime propagation
- promotion pipeline behavior
- server.py structural cleanup
- public agent MCP contract work already landed in prior commits

## What changed

### 1. Project-scoped runtime memory/context

- `project_id` was added to runtime memory source metadata and to the `memory_records` table.
- context retrieval APIs now accept a `project_id`.
- EvoMap runtime retrieval now hard-filters by `scope_project` when a project scope is requested.
- work-memory scope selection prefers narrower project-specific scopes where available.
- planning knowledge ingress in `routes_agent_v3.py` now derives and passes `project_id` into `build_active_context()` so planning receipts do not bypass the new project-aware scope path.

### 2. Authority-anchor precedence

- advisor `available_inputs` now render authority-anchor fields first, under an explicit highest-priority section.
- prompt assembly now prepends an instruction that authority-anchor content wins over retrieved memory, KB, or graph context on conflict.
- prompt section ordering now places EvoMap knowledge ahead of lower-priority generic knowledge.

## Expected behavior

1. The same query under different `project_id` values should yield different scoped recall where project-scoped memory/EvoMap records exist.
2. Unscoped/global memory should remain visible as fallback unless explicitly excluded by the caller.
3. Authority-anchor material should be preserved and clearly ordered ahead of supplemental context.
4. Existing non-project-scoped callers should remain backward compatible.

## Test coverage

Targeted tests:

- `tests/test_routes_agent_v3.py::test_planning_knowledge_ingress_updates_available_inputs_and_context`
- `tests/test_routes_agent_v3_planning_project_scope.py`
- `tests/test_evomap_scope_project.py`
- `tests/test_work_memory_manager.py`
- `tests/test_context_service_work_memory.py`
- `tests/test_task_intake.py`
- `tests/test_prompt_builder.py`
- `tests/test_cognitive_api.py`
- `tests/test_advisor_api.py`
- `tests/test_advisor_runtime.py`

Executed:

```bash
./.venv/bin/pytest -q \
  tests/test_routes_agent_v3.py::test_planning_knowledge_ingress_updates_available_inputs_and_context \
  tests/test_routes_agent_v3_planning_project_scope.py \
  tests/test_evomap_scope_project.py \
  tests/test_work_memory_manager.py \
  tests/test_context_service_work_memory.py \
  tests/test_task_intake.py \
  tests/test_prompt_builder.py \
  tests/test_cognitive_api.py \
  tests/test_advisor_api.py \
  tests/test_advisor_runtime.py
```

Result: pass.

## Review questions for Claude

1. Does the `project_id` threading look complete across the intended hot path, or is there an obvious missing call site in memory/context assembly?
2. Is the `(project_id = ? OR project_id = '')` fallback rule in memory retrieval the right compatibility posture, or should any path be strict-only?
3. Is the `routes_agent_v3._planning_project_scope()` derivation order sound, or should any additional nested context field be considered before this batch lands?
4. Does the current authority-anchor rendering/prompt ordering sufficiently protect frozen facts and style rules from lower-priority retrieved context?
5. Are any of the new scope-hit expectations in `tests/test_work_memory_manager.py` hiding a real semantic regression rather than a legitimate narrowing of scope?
6. Is there any obvious risk that the new EvoMap hard filter on `scope_project` is too aggressive for mixed-scope retrieval scenarios?

## Reviewer focus

Please prioritize:

- data-flow integrity;
- backward compatibility;
- precedence correctness;
- whether any new project-aware scope name reflects a bug versus an intended narrowing.
