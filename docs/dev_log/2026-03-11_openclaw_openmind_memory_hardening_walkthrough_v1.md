# 2026-03-11 OpenClaw/OpenMind Memory Hardening Walkthrough v1

## Scope

Issue: #121

This change hardens the OpenClaw/OpenMind memory integration in four places:

1. Dedup and provenance isolation in `MemoryManager`
2. Cross-session recall boundaries for `captured_memory`
3. Identity forwarding on the OpenClaw advisor slow path
4. Server-side policy gating for memory capture

The deferred follow-up remains unchanged:

- expand capture coverage to assistant decisions and tool results

## What Changed

### 1. Dedup now respects identity boundaries

`MemorySource` now carries `account_id` and `thread_id`, and dedup no longer folds records only by `fingerprint + category`.

The new dedup scope includes:

- `agent`
- `role`
- `session_id`
- `account_id`
- `thread_id`

This prevents cross-session, cross-role, and cross-account record collapse, and stops later writes from overwriting provenance for unrelated captures.

### 2. Captured memory recall is no longer fail-open

`ContextResolver` and `_LocalOnlyContextAssembler` now require identity before cross-session `captured_memory` recall is allowed.

Current behavior:

- same-thread recall: exact `thread_id`
- same-session recall: exact `session_id`
- cross-session recall: only when `account_id` is present and matches
- missing identity: recall blocked and request marked degraded

This removes the prior anonymous/partial-identity cross-session fallback.

### 3. OpenClaw advisor slow path now forwards identity

The `openmind-advisor` extension now forwards runtime identity from OpenClaw context into both:

- `POST /v2/advisor/advise`
- `POST /v2/advisor/ask`

Forwarded fields:

- `session_id`
- `account_id`
- `thread_id`
- `agent_id`

The advisor v3 routes now carry the same fields into:

- `AdvisorAPI.advise(...)`
- graph state for `/v2/advisor/ask`
- created job client metadata for slow-path execution

This removes the previous split where fast-path memory had identity but advisor slow-path defaulted to anonymous/openclaw values.

### 4. Memory capture now has a server-side quality gate

`MemoryCaptureService` now runs `PolicyEngine.run_quality_gate(...)` before writing episodic memory.

Effects:

- sensitive content is blocked server-side even if plugin-side regex misses it
- blocked capture returns structured `quality_gate` details
- blocked capture emits `memory.capture.blocked`
- successful capture also returns `quality_gate`

This aligns capture behavior with existing governed ingest behavior.

## Validation

Targeted and regression tests passed:

- `tests/test_memory_tenant_isolation.py`
- `tests/test_role_pack.py`
- `tests/test_substrate_contracts.py`
- `tests/test_cognitive_api.py`
- `tests/test_openmind_memory_business_flow.py`
- `tests/test_advisor_v3_end_to_end.py`
- `tests/test_openclaw_cognitive_plugins.py`

Additional focused checks added:

- advisor route identity forwarding
- OpenClaw plugin source assertions for forwarded identity
- server-side blocking of sensitive memory capture without persistence

## Notes

GitNexus impact before edits flagged:

- `MemoryManager`: `CRITICAL`
- `ContextResolver`: `HIGH`
- `_capture_one`: `CRITICAL`

The implementation intentionally kept semantic changes localized to existing integration boundaries instead of changing the policy engine itself.
