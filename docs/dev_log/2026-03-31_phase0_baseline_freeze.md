# Phase 0 Baseline Freeze — opencli/CLI-Anything Integration

**Date**: 2026-03-31
**Branch**: `feat/opencli-cli-anything-integration-20260331`
**Worktree**: `/vol1/1000/worktrees/chatgptrest-opencli-integration`
**Implementation Plan**: `/vol1/1000/projects/planning/docs/2026-03-31_ChatgptREST_opencli_CLI-Anything_集成实施计划_v2.md`

## Purpose

This document freezes the current behavior of critical ChatgptREST components before Phase 1 implementation begins. It serves as the baseline for regression testing and rollback validation.

## Frozen Architectural Decisions (D1-D6)

| Decision | Conclusion | Impact |
|----------|-----------|--------|
| D1 | Phase 1 不做全局 `CapabilityExecutorRegistry` | 先做窄 lane 和 subprocess POC |
| D2 | `opencli` 不是 provider family | 不改 `providers/registry.py` 的 provider 枚举 |
| D3 | `OpenCLIExecutor` 第一版必须是 subprocess | 不深度耦合 Node 内部模块 |
| D4 | `CLI-Anything` 不直接写 canonical registry | 先走 candidate intake、review evidence、quarantine |
| D5 | `skill_suite_review_plane` 只当证据平面 | 不把它写成 authority intake |
| D6 | `image / consult / direct Gemini` 在前两阶段不动 | 降低回归面 |

## 1. routes_agent_v3.py — 4 Critical Routing Branches

**File**: `chatgptrest/api/routes_agent_v3.py`
**Main Endpoint**: Line 2416 `@router.post("/turn")`

### Branch 1: Image Generation (Line 3097-3182)

**Trigger**: `goal_hint == "image"`

**Behavior**:
- Directly routes to `gemini_web.generate_image`
- Creates run_id: `f"run_{uuid.uuid4().hex[:12]}"`
- Submits direct job via `_submit_direct_job()`
- Job kind: `"gemini_web.generate_image"`
- Idempotency key: `f"agent-image:{session_id}:{int(time.time())}"`

**Key Code**:
```python
if goal_hint == "image":
    run_id = f"run_{uuid.uuid4().hex[:12]}"
    job_id = _submit_direct_job(
        cfg=cfg,
        kind="gemini_web.generate_image",
        input_obj={
            "prompt": enriched_message,
            **({"file_paths": list(file_paths)} if file_paths else {}),
        },
        params_obj={"timeout_seconds": timeout_seconds},
        client_obj={"name": "agent_v3", "goal_hint": goal_hint, "session_id": session_id},
        idempotency_key=f"agent-image:{session_id}:{int(time.time())}",
    )
```

**Frozen Behavior**:
- Must NOT be affected by opencli integration
- Must continue to route directly to gemini_web.generate_image
- Must preserve idempotency key format
- Must preserve job submission contract

### Branch 2: Consultation (Line 3184-3264)

**Trigger**: `goal_hint in {"consult", "dual_review"}`

**Behavior**:
- Routes to consultation path via `_submit_consultation()`
- Supports file_paths attachment
- Uses session_id for tracking
- Returns consultation result directly

**Key Code**:
```python
if goal_hint in {"consult", "dual_review"}:
    consultation = _submit_consultation(
        cfg=cfg,
        question=enriched_message,
        file_paths=list(file_paths) if file_paths else None,
        timeout_seconds=timeout_seconds,
        session_id=session_id,
        goal_hint=goal_hint,
        user_id=user_id,
    )
```

**Frozen Behavior**:
- Must NOT be affected by opencli integration
- Must continue to use `_submit_consultation()` helper
- Must preserve consultation contract
- Must support both "consult" and "dual_review" goal hints

### Branch 3: Direct Gemini Lane (Line 3266-3361)

**Trigger**: `_should_use_direct_gemini_lane(provider_request, goal_hint)`

**Behavior**:
- Checks if direct Gemini execution is required
- Determines route_name and params_obj via `_gemini_execution_spec()`
- Submits direct job with Gemini-specific configuration
- Bypasses controller path

**Key Code**:
```python
if _should_use_direct_gemini_lane(provider_request=provider_request, goal_hint=goal_hint):
    route_name, params_obj = _gemini_execution_spec(
        provider_request=provider_request,
        strategy_plan=strategy_plan,
        goal_hint=goal_hint,
        timeout_seconds=timeout_seconds,
    )
```

**Frozen Behavior**:
- Must NOT be affected by opencli integration
- Must preserve `_should_use_direct_gemini_lane()` decision logic
- Must preserve `_gemini_execution_spec()` parameter generation
- Must continue to bypass controller when triggered

### Branch 4: Controller Path (Line 3363+)

**Trigger**: Default path when no other branch matches

**Behavior**:
- Creates `ControllerEngine(state)`
- Defines route_mapping with 11 route types:
  - `kb_answer`, `quick_ask`, `clarify`, `hybrid`: auto preset
  - `analysis_heavy`, `funnel`, `build_feature`: thinking_heavy preset
  - `deep_research`: deep_research preset
  - `report`, `write_report`: pro_extended preset
  - `action`: auto preset
- All routes currently map to `chatgpt_web.ask`
- Calls `controller.ask()` with full parameter set
- Waits for delivery via `_wait_for_controller_delivery()`
- Builds agent response with provenance tracking

**Key Code**:
```python
controller = ControllerEngine(state)
route_mapping = {
    "kb_answer": {"provider": "chatgpt", "preset": "auto", "kind": "chatgpt_web.ask"},
    "quick_ask": {"provider": "chatgpt", "preset": "auto", "kind": "chatgpt_web.ask"},
    "clarify": {"provider": "chatgpt", "preset": "auto", "kind": "chatgpt_web.ask"},
    "hybrid": {"provider": "chatgpt", "preset": "auto", "kind": "chatgpt_web.ask"},
    "analysis_heavy": {"provider": "chatgpt", "preset": "thinking_heavy", "kind": "chatgpt_web.ask"},
    "deep_research": {"provider": "chatgpt", "preset": "deep_research", "kind": "chatgpt_web.ask"},
    "report": {"provider": "chatgpt", "preset": "pro_extended", "kind": "chatgpt_web.ask"},
    "write_report": {"provider": "chatgpt", "preset": "pro_extended", "kind": "chatgpt_web.ask"},
    "funnel": {"provider": "chatgpt", "preset": "thinking_heavy", "kind": "chatgpt_web.ask"},
    "build_feature": {"provider": "chatgpt", "preset": "thinking_heavy", "kind": "chatgpt_web.ask"},
    "action": {"provider": "chatgpt", "preset": "auto", "kind": "chatgpt_web.ask"},
}
```

**Frozen Behavior**:
- This is where Phase 2 opencli narrow lane will be inserted
- Must preserve all existing route_mapping entries
- Must preserve controller.ask() contract
- Must preserve provenance building logic
- Must preserve memory capture behavior

**Phase 2 Insertion Point**:
- After line 3361 (after direct Gemini branch)
- Before line 3363 (before controller creation)
- Check for `task_intake.context.execution_request.executor_kind == "opencli"`
- If matched, route to OpenCLIExecutor instead of controller

## 2. providers/registry.py — Provider Enumeration

**File**: `chatgptrest/providers/registry.py`

### Current Provider Specs (Line 51-70)

**Frozen Provider List**:
1. **chatgpt** (Line 52-60)
   - kind_namespace: `"chatgpt_web."`
   - ask_kind: `"chatgpt_web.ask"`
   - rate_limit_key: `"chatgpt_web_send"`
   - supported_presets: `{"auto", "pro_extended", "thinking_heavy", "thinking_extended", "deep_research"}`

2. **gemini** (Line 61-69)
   - kind_namespace: `"gemini_web."`
   - ask_kind: `"gemini_web.ask"`
   - rate_limit_key: `"gemini_web_send"`
   - supported_presets: `{"pro", "deep_think"}`

**Removed Providers** (Line 76):
- `qwen_web.ask` — retired, no longer available

**Frozen Behavior**:
- `_PROVIDER_SPECS` tuple must NOT be modified in Phase 1-2
- opencli is NOT a provider and must NOT be added to this registry
- Provider enumeration remains exactly 2 entries: chatgpt, gemini
- All provider-related functions continue to work only with these 2 providers

**Key Functions**:
- `provider_specs()` → returns frozen 2-provider tuple
- `web_ask_kinds()` → returns `{"chatgpt_web.ask", "gemini_web.ask"}`
- `is_web_ask_kind()` → only recognizes chatgpt/gemini ask kinds
- `provider_spec_for_ask_kind()` → only maps chatgpt/gemini kinds

## 3. completion_contract.py — Answer Artifact Behavior

**File**: `chatgptrest/core/completion_contract.py`

### Contract Version (Line 7-8)

**Frozen Versions**:
- `COMPLETION_CONTRACT_VERSION = "v1"`
- `CANONICAL_ANSWER_VERSION = "v1"`

### Answer State Classification (Line 128-149)

**Frozen Answer States**:
1. **final** — completed with final quality
2. **provisional** — completed but non-final, or terminal status with content
3. **partial** — in-progress or terminal status without content

**State Decision Logic**:
```python
if normalized_status == "completed":
    if _completed_quality_is_non_final(quality):
        answer_state = "provisional"
    else:
        answer_state = "final"
elif normalized_status == "needs_followup":
    answer_state = "provisional" if (research_contract or answer_chars_int > 0 or export_available or research_blocked) else "partial"
elif normalized_status in {"blocked", "error", "canceled", "cancelled"}:
    answer_state = "provisional" if (answer_chars_int > 0 or export_available or research_blocked) else "partial"
elif normalized_status in {"in_progress", "queued", "cooldown"}:
    if last_event in {"completion_guard_downgraded", "completion_guard_research_contract_blocked"}:
        answer_state = "provisional"
    else:
        answer_state = "partial"
```

**Frozen Behavior**:
- Phase 1-2 must NOT modify contract version
- opencli execution results must conform to existing answer state classification
- opencli must generate answer artifacts compatible with this contract
- `answer_path`, `conversation_export_path`, `widget_export_available` semantics preserved

**Phase 1-2 Compatibility Strategy**:
- opencli execution generates local answer artifact (answer.md)
- opencli result.json provides structured_result
- opencli diagnostics.json provides execution metadata
- `conversation_url` left empty (not faked)
- Answer state determined by opencli exit code mapping

## 4. market_gate.py — Candidate/Quarantine Lifecycle

**File**: `chatgptrest/kernel/market_gate.py`

### Database Schema (Line 24-91)

**Frozen Tables**:

1. **capability_gaps** (Line 25-45)
   - Primary key: `gap_id`
   - Unique key: `gap_key`
   - Status values: `"open"` (default), others TBD
   - Priority values: `"P2"` (default), others TBD
   - Source: `"resolver"` (default)

2. **capability_gap_events** (Line 54-66)
   - Links to capability_gaps via `gap_id`
   - Tracks trace_id, session_id, agent_id
   - Records unmet capabilities and context

3. **market_skill_candidates** (Line 73-87)
   - Primary key: `candidate_id`
   - Status: `"quarantine"` (default)
   - Trust level: `"unreviewed"` (default)
   - Quarantine state: `"pending"` (default)
   - Links to gaps via `linked_gap_id`
   - Evidence stored in `evidence_json`

### Data Classes (Line 105-163)

**Frozen Structures**:

1. **CapabilityGap** (Line 105-129)
   - Tracks unmet capability requirements
   - Records hit_count, latest trace/session/agent
   - Stores context as dict

2. **MarketSkillCandidate** (Line 131-149)
   - Represents external skill candidate
   - Links to capability_ids (list)
   - Stores evidence as dict
   - Tracks quarantine lifecycle

3. **QuarantineDecision** (Line 151-163)
   - Decision object for quarantine gate
   - Fields: allowed, skill_id, platform, maturity, quarantine_required, trust_level, reason

**Frozen Behavior**:
- Phase 1-2 must NOT modify schema
- CLI-Anything outputs enter as `market_skill_candidates` with status="quarantine"
- Candidates remain in quarantine until manual promotion
- Canonical registry updates remain manual, append-only
- Gap linking via `linked_gap_id` preserved

**Phase 5 Integration Point**:
- CLI-Anything manifest → `market_skill_candidates` table
- Validation bundle → review evidence plane (separate from market_gate)
- Promotion to canonical registry requires owner approval
- No automatic promotion in Phase 5

## Critical Test List

### Regression Tests (Must Pass)

1. **Image Generation**
   - `goal_hint="image"` routes to gemini_web.generate_image
   - Idempotency key format preserved
   - Job submission contract unchanged

2. **Consultation**
   - `goal_hint="consult"` routes to consultation path
   - `goal_hint="dual_review"` routes to consultation path
   - File attachment support preserved

3. **Direct Gemini**
   - `_should_use_direct_gemini_lane()` decision logic unchanged
   - Gemini execution spec generation preserved
   - Controller bypass behavior preserved

4. **Controller Path**
   - All 11 route types map correctly
   - route_mapping structure unchanged
   - Provenance tracking preserved
   - Memory capture behavior preserved

5. **Provider Registry**
   - Only 2 providers: chatgpt, gemini
   - `web_ask_kinds()` returns exactly 2 kinds
   - `qwen_web.ask` remains removed
   - No new providers added

6. **Completion Contract**
   - Contract version remains "v1"
   - Answer state classification logic unchanged
   - final/provisional/partial states work correctly

7. **Market Gate**
   - Schema unchanged
   - Candidate status="quarantine" by default
   - Gap recording works
   - No automatic promotion

### Phase 1 Validation (After OpenCLIExecutor)

1. **Subprocess Execution**
   - Binary not found → clear error
   - Invalid args → usage_error classification
   - JSON parse failure → execution_error
   - Timeout → temporary_failure
   - Exit code 69/75 → retryable
   - Exit code 77 → auth_required

2. **Artifact Generation**
   - request.json created
   - stdout.txt captured
   - stderr.txt captured
   - result.json with structured_result
   - diagnostics.json with metadata
   - doctor.txt on failure

3. **No Regression**
   - All 7 regression tests still pass
   - No provider registry changes
   - No completion contract changes
   - No market gate schema changes

### Phase 2 Validation (After Narrow Lane)

1. **Explicit opencli Request**
   - `execution_request.executor_kind == "opencli"` triggers opencli lane
   - Policy validation enforced
   - No silent fallback to provider web
   - Answer artifact compatible with completion contract

2. **No Implicit Routing**
   - Requests without `execution_request` unchanged
   - Image/consult/direct Gemini branches unaffected
   - Controller path behavior preserved for non-opencli requests

3. **Provenance Tracking**
   - `route="opencli"` recorded
   - `final_provider="opencli"` recorded
   - `provider_selection` not faked

## Files NOT to Modify (Phase 1-2)

1. `chatgptrest/providers/registry.py` — provider enumeration frozen
2. `chatgptrest/core/job_store.py` — job lifecycle unchanged
3. `chatgptrest/core/completion_contract.py` — contract version frozen
4. `chatgptrest/evomap/knowledge/skill_suite_review_plane.py` — evidence plane only
5. `ops/policies/skill_platform_registry_v1.json` — canonical authority frozen

## Rollback Criteria

If any of these occur, Phase 1-2 must be rolled back:

1. Any of the 4 routing branches regresses
2. Provider registry modified
3. Completion contract version changed
4. Market gate schema modified
5. opencli lane causes silent fallback to provider web
6. Unapproved candidates enter canonical registry
7. Artifact completeness < 100%

## Next Steps

After this baseline is frozen:

1. **Phase 1**: Implement `OpenCLIExecutor` subprocess wrapper
   - New files: `opencli_contracts.py`, `opencli_policy.py`, `opencli_executor.py`
   - Operator smoke test: `ops/run_opencli_executor_smoke.py`
   - Unit tests: `tests/test_opencli_executor.py`

2. **Phase 2**: Add explicit opencli narrow lane to `routes_agent_v3.py`
   - Insert after line 3361, before line 3363
   - Check `task_intake.context.execution_request`
   - Route to OpenCLIExecutor if matched
   - Integration test: `tests/test_routes_agent_v3_opencli_lane.py`

## Verification

This baseline freeze is complete when:

- [ ] All 4 routing branches documented
- [ ] Provider registry frozen (2 providers only)
- [ ] Completion contract behavior documented
- [ ] Market gate lifecycle documented
- [ ] Critical test list created
- [ ] No-modify file list created
- [ ] Rollback criteria defined
- [ ] This document committed to git

**Status**: ✅ Complete
**Commit**: Pending
