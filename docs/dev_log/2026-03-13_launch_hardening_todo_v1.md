# Launch Hardening Todo v1

## Baseline

- [x] create clean worktree from `origin/master`
- [x] rerun full `pytest -q` baseline
- [x] identify current failing tests
- [x] re-check current blocker issues against code

## Current failing tests

- [ ] `tests/test_evolution_queue.py::TestPlanExecutor::test_execute_rolls_back_partial_changes`
- [ ] `tests/test_execution_experience_review_validation_failure_fixture_bundle.py::test_execution_experience_review_validation_failure_fixture_bundle_complete_required`
- [ ] `tests/test_execution_experience_review_validation_failure_fixture_bundle.py::test_execution_experience_review_validation_failure_fixture_bundle_valid_required`
- [ ] `tests/test_mcp_tool_registry_snapshot.py::test_mcp_tool_registry_snapshot`
- [ ] `tests/test_sandbox.py::TestMergeBack::test_merge_back_sets_staged_status`
- [ ] `tests/test_sandbox.py::TestMergeBack::test_merge_all_new_atoms`

## Security blockers

- [ ] fix full-document redact scan in `chatgptrest/advisor/report_graph.py`
- [ ] route Google Docs create through effects outbox
- [ ] route Gmail send through effects outbox
- [ ] add redact tail-section regression tests
- [ ] add duplicate side-effect / retry safety tests
- [ ] add attachment-contract fail-closed guard before provider send

## Knowledge blockers

- [ ] stop default retrieval from serving `STAGED` atoms
- [ ] decide default allowed promotion statuses
- [ ] wire `mark_atoms_used()` into result-return path
- [ ] wire feedback capture into retrieval lifecycle
- [ ] fix consult telemetry DDL divergence
- [ ] add auto-promotion path for activity ingest
- [ ] verify authority resolution contract across consult/runtime/cognitive

## Runtime honesty and scope

- [ ] fix `/v2/cognitive/health` `ok=true + status=not_initialized`
- [ ] update readiness docs for merged `#160/#164`
- [ ] keep Qwen out of launch surface
- [ ] decide Gemini supported mode set for launch

## Validation gates

- [ ] `pytest -q` all green
- [ ] targeted security / knowledge regressions green
- [ ] convergence runner green
- [ ] supported-provider live validation green
- [ ] bounded soak green
- [ ] long soak / canary evidence recorded
