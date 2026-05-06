# 2026-03-11 OpenMind Delivery Hardening Walkthrough v1

## Goal

Harden the OpenMind "business request -> advisor execution -> report/funnel delivery" path so the default OpenClaw entrypoint matches the structured advisor path, runtime identity/context reaches the graph, and report/funnel execution uses the live runtime policy/outbox objects instead of falling back to implicit side effects.

## Changes

### Commit `dce39db` — `Harden OpenMind advisor entry routing`

- Switched the OpenClaw `openmind-advisor` plugin default mode from `ask` to `advise`.
- Added runtime context forwarding in the plugin:
  - `session_id`
  - `user_id`
  - merged OpenClaw context fields
- Added stable async `ask` idempotency derivation in the plugin.
- Updated `/v2/advisor/advise` to forward `session_id`, `user_id`, `context`, and optional `trace_id` into `AdvisorAPI.advise(...)`.
- Updated `/v2/advisor/ask` auto idempotency generation to include:
  - question
  - intent hint
  - role id
  - session id
  - user id
  - context
- Updated the OpenClaw rebuild baseline so generated `openmind-advisor` config defaults to `advise`.
- Added tests covering:
  - `advise` forwarding of session/user/context
  - `ask` idempotency stability across same session/context and divergence across different session/context
  - plugin source assertions
  - rebuild default mode assertions

### Commit `d275976` — `Wire OpenMind report and funnel delivery runtime`

- Updated `execute_report(...)` to inject live runtime services into `report_graph`:
  - `llm_connector`
  - `kb_hub`
  - `_policy_engine`
  - `_effects_outbox`
  - `_delivery_target`
- Updated `execute_funnel(...)` to construct `AgentDispatcher` with the live runtime outbox.
- Tightened `report_graph.finalize(...)` so external exports only happen when explicitly requested:
  - Google Docs / Gmail only when `_delivery_target == "google_drive"`
  - Obsidian only when `_delivery_target == "obsidian"`
- Fixed the `execute_report(...)` local `trace` variable so episodic memory writeback does not depend on the KB writeback branch to define it.
- Added tests covering:
  - `finalize(...)` skipping side effects without an explicit delivery target
  - `execute_report(...)` runtime service injection
  - `execute_funnel(...)` runtime outbox injection

## Validation

### Targeted suites

Passed:

- `./.venv/bin/pytest -q tests/test_advisor_v3_end_to_end.py tests/test_openclaw_cognitive_plugins.py tests/test_rebuild_openclaw_openmind_stack.py`
- `./.venv/bin/pytest -q tests/test_report_graph.py tests/test_funnel_kb_writeback.py`
- `./.venv/bin/pytest -q tests/test_advisor_v3_end_to_end.py tests/test_openclaw_cognitive_plugins.py tests/test_rebuild_openclaw_openmind_stack.py tests/test_report_graph.py tests/test_funnel_kb_writeback.py tests/test_phase5_e2e.py`

### Full suite

Command run:

- `./.venv/bin/pytest -q`

Result:

- full suite is **not green**
- failures observed: 6
- failure modules:
  - `tests/test_evolution_queue.py`
  - `tests/test_execution_experience_review_validation_failure_fixture_bundle.py`
  - `tests/test_mcp_tool_registry_snapshot.py`
  - `tests/test_sandbox.py`

Observed failure signatures:

- SQLite savepoint rollback errors in EvoMap evolution/sandbox flows
- fixture summary mismatch in execution experience review validation
- MCP tool registry snapshot drift

These failures are outside the files changed in this task and were not introduced by the advisor entry/delivery hardening patches. They remain blockers for claiming a repository-wide green state.

## Outcome

This task hardens the OpenMind advisor entry and delivery chain and leaves the branch with:

- default OpenClaw advisor entry aligned to structured `advise`
- request identity/context propagated end to end
- async `ask` idempotency scoped by session/user/context
- report/funnel execution using runtime policy/outbox services
- report delivery side effects gated by explicit delivery target

Repository-wide release readiness still depends on resolving the 6 unrelated global pytest failures listed above.
