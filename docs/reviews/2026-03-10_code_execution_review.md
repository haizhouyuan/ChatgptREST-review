# Code Execution Review — 2026-03-10

## Scope
Review of **22 commits** (`ee7787c..39cb931`) since Issue #110 review baseline.  
**75 files changed**, **+5785 / -301 lines**.  
GitNexus `detect_changes` vs `origin/master`: **43 changed symbols, 35 affected processes, CRITICAL risk level**.

## Test Results

```
914 passed, 1 failed, 14 skipped (2m21s)
```

### Failure Analysis

| Test | File:Line | Expected | Actual | Root Cause |
|------|-----------|----------|--------|------------|
| `test_retryable_qwen_cdp_limit_becomes_needs_followup` | `test_leases.py:355` | 200 | 409 | New `_enforce_kind_runtime_availability()` gate in `routes_jobs.py` rejects `qwen_web.*` when `CHATGPTREST_QWEN_ENABLED` unset. Test missing `monkeypatch.setenv("CHATGPTREST_QWEN_ENABLED", "1")`. |

**Severity**: Minor — test environment setup gap, not a production bug. The gate itself is correct behavior.

## Issue #110 Review Items — Execution Status

### ✅ Completed

| Item | Commit | Evidence |
|------|--------|----------|
| PYTHONPATH footgun → `conftest.py` fix | `e243c1a` → `528fe15` | `sys.path.insert(0, ROOT)` in `tests/conftest.py` |
| Memory capture vertical slice (all 3 checkpoints) | `10ace71` | `memory_capture_service.py` (186L) + 3 tests in `test_cognitive_api.py` |
| CP1: Capture → Ingest → Dedup with audit | `10ace71` | `test_memory_capture_dedups_and_emits_audit_evidence` |
| CP2: Cross-session recall → ContextBlock | `10ace71` | `test_context_resolve_includes_cross_session_captured_memory_block` |
| CP3: Runtime reset persistence + audit trail | `10ace71` | `test_memory_capture_persists_across_runtime_reset_with_audit_trail` |
| Funnel graph LLM stubs (test isolation) | `8a89fd6` | `_stub_funnel_llm()` in `test_funnel_graph.py` |
| Duplicate path resolvers consolidation | `528fe15` | `openmind_paths.py` (91L) replaces inline resolvers in `routes_consult.py` |
| Advisor auth hardening | `c2a76d7` | `_enforce_advisor_auth_baseline()` |
| QA inspector write guards | `cc6aa17` | QA submission gating |
| Gemini wait family splits | `777d67b` | Stable thread back-off |
| Issue families + stuck wait health | `39cb931` | `routes_ops.py` +79L |
| KB hot path latency guard | `7283b0a` | Direct path caching |

### 🔲 Not Yet Addressed (from Issue #110 three-lane plan)

| Lane | Item | Status |
|------|------|--------|
| Baseline UX/Ops | `/health` quick endpoint | Not implemented |
| Baseline UX/Ops | One-command mode switch (lean/ops) | Not implemented |
| Baseline UX/Ops | guardian/maintagent/verifier boundary doc | Not implemented |
| Architecture Debt | Funnel stage gates (`should_continue_after_a/b`) connected to runtime | Dead code still dead |
| Architecture Debt | PromotionEngine connected to production pipeline | Still disconnected |
| Architecture Debt | `_run_once` decomposition (2353L) | Still monolithic |
| Architecture Debt | `get_advisor_runtime` weight reduction | Slightly modified (+34/-35) but still >500L |

## New Code Quality Observations

### Positive
1. **`MemoryCaptureService`** is clean: single responsibility, proper error handling, identity gap detection, structured audit trail + EventBus integration.
2. **`openmind_paths.py`** consolidation eliminates the duplicate path resolution problem identified in our review.
3. **Test coverage growth**: 914 tests (+~40 from review baseline), covering memory capture round-trip, funnel graph with LLM mocks, QA inspector, ops endpoints.

### Concerns
1. **Runtime availability gate test gap**: The new `_enforce_kind_runtime_availability()` function creates a legitimate runtime-disable feature, but the test that exercises the Qwen job flow wasn't updated. This pattern of "add defensive code in production path, forget to update all test fixtures" is a systemic risk given the test suite size.
2. **GitNexus risk: CRITICAL**: The delta vs `origin/master` touches `routes_issues.py` heavily (20 symbols modified) and affects 35 execution processes. This is expected for the issue families feature but signals the issue domain is becoming the highest-complexity surface.
3. **`_run_once` grew**: `worker.py` gained +49 lines, making the monolithic function slightly larger, not smaller.

## Verdict

**Execution quality: Good.** The memory capture vertical slice was implemented faithfully to the 3-checkpoint plan discussed in Issue #110. The PYTHONPATH and path consolidation items were completed. The single test failure is a minor fixture gap, not a logic bug. The items that remain are the larger architecture debt items which were explicitly deferred.

**Immediate fix needed**: Add `monkeypatch.setenv("CHATGPTREST_QWEN_ENABLED", "1")` to `test_retryable_qwen_cdp_limit_becomes_needs_followup` in `test_leases.py`.
