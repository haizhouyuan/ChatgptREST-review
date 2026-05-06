# 2026-04-03 Gemini Wait Thread Reopen Execution Review v2

## 1. Scope

This batch is narrower than `v1`.

It only freezes the latest four-file hardening around:

1. runtime compact-planning answer normalization trust boundary
2. consult snapshot-answer regression coverage
3. Gemini wait recovery-budget assertion hardening
4. matching local tests and redteam follow-up

## 2. What Changed In This Batch

### 2.1 Compact normalization trust boundary was tightened

`chatgptrest/api/routes_agent_v3.py` now keeps compact normalization behind runtime-selected scenario-pack data.

The normalization gate no longer trusts caller-supplied `task_intake.context.planning_mode` or `planning_profile`.

The current behavior is:

1. only normalize when runtime `scenario_pack.provider_hints.planning_mode == compact_next_steps`
2. and runtime `scenario_pack.profile == implementation_plan`
3. otherwise preserve the original three-line answer text

### 2.2 Consult regression coverage was added

The `consult` branch now remains explicitly covered by test after the earlier undefined `normalized_answer` regression.

The branch continues to return the consultation snapshot answer directly.

### 2.3 Gemini wait budget assertions were pinned

`tests/test_gemini_wait_sidebar_thread_guard.py` no longer uses loose `>= 2` assertions.

The current envelope is now explicitly pinned in both success and failure cases:

1. `requested_cid_loop_reopen_total_attempts == 2`
2. `requested_cid_total_recovery_attempts == 3`
3. same-session repair still occurs once
4. wrong-thread mismatch still fail-closes

## 3. Validation Run

The following checks were rerun and passed:

1. `python3 -m py_compile chatgptrest/api/routes_agent_v3.py tests/test_routes_agent_v3.py chatgpt_web_mcp/providers/gemini/wait.py tests/test_gemini_wait_sidebar_thread_guard.py`
2. `./.venv/bin/pytest -q tests/test_routes_agent_v3.py -k 'consult_lane_returns_snapshot_answer or compact_normalization_requires_implementation_plan_profile or compact_implementation_next_steps'`
3. `./.venv/bin/pytest -q tests/test_gemini_wait_sidebar_thread_guard.py tests/test_gemini_wait_conversation_url_upgrade.py tests/test_gemini_wait_conversation_hint.py`

## 4. Current Independent Judgment

My current judgment after this batch is:

1. the compact implementation-plan path is still only locally proven, not yet newly live-proven
2. the normalization helper is now behind the correct runtime trust boundary
3. the consult regression is closed
4. Gemini wait recovery remains fail-closed and its current retry envelope is now explicit in tests
5. the front live blocker still remains Gemini thread persistence until a new live-completion run proves otherwise

## 5. One-Line Conclusion

> `v2` should be read as: compact-planning normalization and Gemini wait retry semantics are now more tightly specified, the consult regression is covered, and the live blocker mouthpiece remains unchanged until fresh evidence says otherwise.
