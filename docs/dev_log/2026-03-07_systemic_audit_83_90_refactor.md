# 2026-03-07 Systemic Audit #83-#90 Refactor

Branch: `codex/systemic-audit-83-90`

## Goal

Use a small number of coherent refactors to close the architectural issues behind `#83` through `#90`:

- shared parsing/executor seams instead of worker-local duplication
- safer completion-state convergence for job artifacts
- explicit advisor runtime + single routing stack
- shared control-plane helpers for MCP and ops flows

## Phase 1

Status: completed

Changes:

- added `chatgptrest/core/conversation_exports.py` as the shared conversation-export parsing layer
- added `chatgptrest/executors/factory.py` as the executor resolution seam
- updated `chatgptrest/worker/worker.py` to consume those shared seams while keeping worker-compatible wrapper names
- updated `ops/verify_job_outputs.py` to use the shared export parsing logic instead of its own drift-prone normalizer

Why:

- addresses `#84` and `#85` by removing worker-owned parsing/executor mapping from the monolithic loop
- addresses part of `#90` by aligning ops verification semantics with worker reconciliation semantics

Verification:

- `./.venv/bin/python -m py_compile chatgptrest/core/conversation_exports.py chatgptrest/executors/factory.py chatgptrest/worker/worker.py ops/verify_job_outputs.py`
- `./.venv/bin/pytest -q tests/test_conversation_export_reconcile.py tests/test_deep_research_response_envelope.py tests/test_worker_and_answer.py -q`

## Phase 2

Status: verified in branch baseline

Observed baseline:

- `chatgptrest/core/job_store.py` already stages `answer.*` and `result.json`, publishes files, and only then flips DB state to `completed`
- `chatgptrest/core/artifacts.py` already exposes `write_result_staged(...)`
- `tests/test_contract_v1.py` already contains a regression that forces a transition failure and asserts staged/published files are cleaned up

Why it still matters for this audit:

- `#83` is the strongest correctness issue in the audit set, so the first branch pass explicitly re-validated the write boundary before landing broader runtime/control-plane work
- keeping the verification in the walkthrough makes it clear this branch is building on an inherited fix instead of silently assuming the split-brain window is gone

Verification:

- `./.venv/bin/python -m py_compile chatgptrest/core/artifacts.py chatgptrest/core/job_store.py tests/test_contract_v1.py`
- `./.venv/bin/pytest -q tests/test_contract_v1.py -q`

## Phase 3

Status: completed

Changes:

- added `chatgptrest/advisor/runtime.py` as the dedicated Advisor composition root
- reduced `chatgptrest/api/routes_advisor_v3.py::_init_once()` to runtime lookup instead of re-bootstrapping the full Advisor stack in-route
- updated `chatgptrest/advisor/graph.py`, `report_graph.py`, and `funnel_graph.py` to resolve services through the runtime/registry seam while keeping test injection paths
- updated `chatgptrest/kernel/llm_connector.py` to accept injected `RoutingFabric` and signal emitters instead of importing Advisor globals
- switched `/v2/advisor/routing-stats` to `RoutingFabric.status()` so the API stops presenting `ModelRouter` as the source of truth

Why:

- addresses `#87` by moving Advisor bootstrap out of the route file and shrinking the god-router surface
- addresses `#89` by making `RoutingFabric` the primary runtime path and removing the legacy `ModelRouter + McpLlmBridge` selection chain from `advisor.graph`
- addresses part of `#88` by routing graph KB writeback through the shared `KBWritebackService`

Verification:

- `./.venv/bin/python -m py_compile chatgptrest/advisor/runtime.py chatgptrest/advisor/graph.py chatgptrest/advisor/report_graph.py chatgptrest/advisor/funnel_graph.py chatgptrest/kernel/llm_connector.py chatgptrest/api/routes_advisor_v3.py`
- `./.venv/bin/pytest -q tests/test_funnel_graph.py tests/test_llm_connector.py tests/test_advisor_graph.py tests/test_report_graph.py tests/test_routes_advisor_v3_security.py tests/test_routing_fabric.py -q`
- `./.venv/bin/pytest -q tests/test_advisor_api.py tests/test_advisor_v3_end_to_end.py -q`
- post-phase regression added `reset_advisor_runtime()` plus test-side resets in app-level Advisor suites so singleton runtime no longer leaks `QWEN_API_KEY` configuration across tests

## Phase 4

Status: completed

Changes:

- added `chatgptrest/core/control_plane.py` to centralize API endpoint parsing, localhost checks, port probing, repo-venv Python selection, and local API autostart
- added `chatgptrest/core/repair_jobs.py` to centralize `repair.check` / `repair.autofix` input+params shaping and local DB job creation
- updated `chatgptrest/mcp/server.py` to use the shared control-plane + repair request helpers instead of carrying its own autostart and repair payload logic
- updated `ops/maint_daemon.py` to delegate API autostart and repair job creation to the shared helpers
- updated `chatgptrest/worker/worker.py` to create auto-submitted `repair.autofix` jobs through the shared repair factory
- added regression tests for the new helper layer and tightened existing maint-daemon tests to assert request payload contracts

Why:

- addresses `#86` by pulling hidden MCP control actions out of the adapter file and into explicit shared primitives
- addresses `#90` by removing duplicated autostart/repair job authority from `ops/maint_daemon.py`
- closes more of `#84` / `#85` by stopping worker/MCP/ops from each maintaining their own repair request shape

Verification:

- `./.venv/bin/python -m py_compile chatgptrest/core/control_plane.py chatgptrest/core/repair_jobs.py chatgptrest/mcp/server.py chatgptrest/worker/worker.py ops/maint_daemon.py tests/test_control_plane_helpers.py tests/test_mcp_repair_submit.py tests/test_maint_daemon_auto_repair_check.py`
- `./.venv/bin/pytest -q tests/test_control_plane_helpers.py tests/test_mcp_repair_submit.py tests/test_maint_daemon_auto_repair_check.py tests/test_worker_auto_autofix_submit.py tests/test_mcp_autostart_prefers_venv.py tests/test_repair_check.py -q`

## Phase 5

Status: completed after blocking PR review

Review blockers addressed:

- `store_answer_result()` was still publishing `answer.*` / `result.json` before the lease CAS completed, which let a losing worker overwrite or delete already-published canonical artifacts during a `LeaseLost` race
- `reset_advisor_runtime()` only cleared `_RUNTIME`, while graph execution still fell back to the ambient `_registry`; watcher/subscriber teardown was also incomplete

Changes:

- moved `chatgptrest/core/job_store.py::store_answer_result()` to run `transition(..., dst=completed)` before publishing canonical answer/result files
- limited transition-failure cleanup to attempt-owned staging files, and added a regression that pre-seeds winner canonical artifacts before forcing `LeaseLost`
- added invocation-scoped runtime binding in `chatgptrest/advisor/graph.py` so graph/report/funnel service lookups can use the active `AdvisorRuntime` without serializing live objects into LangGraph state
- expanded `AdvisorRuntime` to expose the same surface the graph expects (`llm_connector`, `evomap_observer`, `kb_registry`, `policy_engine`, etc.) and added explicit cleanup callbacks
- updated `reset_advisor_runtime()` to stop the routing watcher, unsubscribe KB/EventBus/EvoMap actuator handlers, close the checkpoint connection, and clear the legacy registry fallback
- updated `chatgptrest/api/routes_advisor_v3.py` to use the runtime object directly for CC endpoints and to seed manual graph-state routing with `_runtime`
- added `tests/test_advisor_runtime.py` to verify both runtime binding and actual teardown behavior

Why:

- closes the concrete correctness race called out in review on `store_answer_result()` rather than relying on the old empty-canonical regression
- makes the extracted Advisor runtime the real authority during invocation instead of a cosmetic wrapper around ambient globals
- turns `reset_advisor_runtime()` into an actual isolation boundary for tests and runtime reuse

Verification:

- `./.venv/bin/pytest -q tests/test_contract_v1.py -k 'store_answer_result or lease_cas_prevents_old_worker_overwrite or answer_completed_missing_artifact_503'`
- `./.venv/bin/pytest -q tests/test_worker_and_answer.py -k 'store_answer or lease_lost'`
- `./.venv/bin/python -m py_compile chatgptrest/advisor/graph.py chatgptrest/advisor/runtime.py chatgptrest/api/routes_advisor_v3.py`
- `./.venv/bin/pytest -q tests/test_advisor_runtime.py tests/test_advisor_v3_end_to_end.py tests/test_routes_advisor_v3_security.py`
- `./.venv/bin/pytest -q tests/test_funnel_graph.py tests/test_report_graph.py`
- `./.venv/bin/pytest -q tests/test_advisor_graph.py`
- `./.venv/bin/pytest -q tests/test_llm_connector.py -k 'router or select_model'`
- `./.venv/bin/pytest -q tests/test_advisor_api.py tests/test_advisor_orchestrate_api.py tests/test_mcp_advisor_tool.py`
- `./.venv/bin/pytest -q tests/test_advisor_consult.py tests/test_advisor_runs_replay.py`

## Phase 6

Status: completed after follow-up review

Review follow-up:

- `reset_advisor_runtime()` now unwound watcher/subscriber state, but it still left SQLite-backed runtime objects open (`EventBus`, `EffectsOutbox`, `KBHub`, and peers)

Changes:

- extended `AdvisorRuntime.close()` to explicitly close runtime-owned DB-backed resources after callback teardown
- added `chatgptrest/kb/registry.py::ArtifactRegistry.close()` so the registry connection can be released during reset
- extended `tests/test_advisor_runtime.py` to assert runtime reset closes `event_bus`, `outbox`, `kb_hub`, `memory`, `kb_registry`, `observer`, and `evomap_knowledge_db`

Why:

- turns `reset_advisor_runtime()` into a real teardown boundary instead of only a subscription/watcher cleanup helper
- avoids leaking open SQLite handles across repeated reset/recreate cycles in tests or long-lived runtime reuse

Verification:

- `./.venv/bin/python -m py_compile chatgptrest/advisor/runtime.py chatgptrest/kb/registry.py tests/test_advisor_runtime.py`
- `./.venv/bin/pytest -q tests/test_advisor_runtime.py tests/test_advisor_v3_end_to_end.py tests/test_routes_advisor_v3_security.py`
- `./.venv/bin/pytest -q tests/test_kb.py`
