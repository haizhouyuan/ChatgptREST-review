# Code Context Map

## Task Harness / Runtime / Memory / Completion substrate

- `chatgptrest/advisor/task_intake.py`
- `chatgptrest/advisor/task_spec.py`
- `chatgptrest/task_runtime/api_routes.py`
- `chatgptrest/task_runtime/task_initializer.py`
- `chatgptrest/task_runtime/task_store.py`
- `chatgptrest/task_runtime/task_workspace.py`
- `chatgptrest/task_runtime/delivery_integration.py`
- `chatgptrest/task_runtime/memory_distillation.py`
- `chatgptrest/eval/evaluator_service.py`
- `chatgptrest/eval/decision_plane.py`
- `chatgptrest/quality/outcome_ledger.py`
- `chatgptrest/core/completion_contract.py`
- `chatgptrest/core/job_store.py`
- `chatgptrest/kernel/work_memory_manager.py`
- `chatgptrest/kernel/work_memory_importer.py`
- `chatgptrest/cognitive/context_service.py`
- `chatgptrest/repo_cognition/bootstrap.py`
- `chatgptrest/repo_cognition/gitnexus_adapter.py`
- `chatgptrest/repo_cognition/runtime.py`
- `chatgptrest/repo_cognition/obligations.py`
- `chatgptrest/cli.py`

## opencli / CLI-Anything integration

- `chatgptrest/executors/opencli_contracts.py`
- `chatgptrest/executors/opencli_policy.py`
- `chatgptrest/executors/opencli_executor.py`
- `chatgptrest/api/routes_agent_v3.py`
- `ops/build_cli_anything_market_manifest.py`
- `ops/run_opencli_executor_smoke.py`
- `ops/policies/opencli_execution_catalog_v1.json`

## Verification / acceptance / tests

- `tests/test_task_runtime.py`
- `tests/test_opencli_policy.py`
- `tests/test_opencli_executor.py`
- `tests/test_cli_anything_market_manifest.py`
- `tests/test_routes_agent_v3_opencli_lane.py`
- `tests/test_import_skill_market_candidates.py`
- `tests/test_repo_cognition_gitnexus_adapter.py`
- `tests/test_repo_cognition_runtime.py`
- `tests/test_chatgptrest_bootstrap.py`
- `tests/test_doc_obligations.py`
- `tests/test_chatgptrest_closeout.py`

## What changed since the earlier architecture-only review

- Task Runtime foundation is now implemented and merged.
- Repo cognition / bootstrap / obligations / closeout is now implemented and merged.
- opencli / CLI-Anything integration is now implemented, merged, and smoke-tested.
- A real integrated worktree validation surfaced and fixed:
  - worktree-safe canonical repo name resolution for GitNexus
  - list-shaped `opencli` success payload support in live smoke

## What reviewers should judge now

- Is the implemented system now architecturally complete enough?
- Are the remaining gaps still structural, or only rollout/extension items?
- Are any current claims still overstated relative to the actual implementation?
