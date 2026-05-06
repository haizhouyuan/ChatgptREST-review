# 2026-04-04 Gemini CDP new_page retry narrowing review v1

## Summary

This batch narrows Gemini CDP recovery inside `_open_gemini_page()` to one specific bootstrap site: `BrowserContext.new_page()` failures that clearly indicate a closed page/context/browser. It does **not** broaden the retry to `goto` or the rest of `_open_over_cdp()`.

The goal is to absorb the short instability window where local Chrome/CDP is flapping during Gemini page bootstrap, without changing the broader restart/fallback behavior.

## Code Changes

### 1. Narrow retry site in `chatgpt_web_mcp/providers/gemini/core.py`

- Added `_looks_like_closed_cdp_new_page_error()` with explicit `BrowserContext.new_page` / `context.new_page` matching.
- Added `_pick_reusable_cdp_page()` and `_fresh_cdp_browser_context()`.
- Changed `_open_over_cdp()` so the extra local retry only happens when `context.new_page()` fails with an explicit closed-target new-page signature.
- The local retry is now spend-once across the whole `_open_gemini_page()` call, so the post-restart `_open_over_cdp()` path cannot take a second local retry.
- If the local `new_page()` retry still fails, the existing outer `_restart_local_cdp_chrome()` path remains the next step.
- After a fresh retry attach, reuse-enabled Gemini tabs are checked again before forcing a new tab.
- A `TargetClosedError` coming from `_goto_with_retry()` or a generic `*.new_page` string is no longer eligible for this local retry and will continue through the legacy restart/fallback path.

### 2. Added focused regression coverage in `tests/test_gemini_cdp_page_isolation.py`

The new/updated tests freeze five invariants:

1. `new_page()` closed-target failure retries once locally and succeeds without restart.
2. If that local retry also fails, restart still fires exactly once and the legacy path remains intact.
3. The local retry can be spent at most once across the whole `_open_gemini_page()` call, including the post-restart path.
4. After a fresh retry attach, reuse-enabled existing Gemini tabs are rechecked before opening a new tab.
5. A `TargetClosedError` from `goto` or a generic non-BrowserContext `*.new_page` string does not use the new local retry.

## Validation Run

### Targeted unit/regression suites

Passed:

- `python3 -m py_compile chatgpt_web_mcp/providers/gemini/core.py tests/test_gemini_cdp_page_isolation.py`
- `./.venv/bin/pytest -q tests/test_gemini_cdp_page_isolation.py tests/test_gemini_idempotency_replay_recovery.py tests/test_gemini_wait_sidebar_thread_guard.py tests/test_gemini_wait_conversation_url_upgrade.py tests/test_gemini_wait_conversation_hint.py tests/test_gemini_wait_param_compat.py`
- `./.venv/bin/pytest -q tests/test_chatgpt_cdp_page_reuse.py tests/test_cdp_ws_fallback.py tests/test_gemini_infra_retry.py`

## Live Reality Check

A live OpenClawBot planning completion gate rerun was attempted during this batch with:

- `CHATGPTREST_EVAL_OUT_DIR=docs/dev_log/artifacts/openclawbot_planning_task_plane_live_completion_gate_20260404_v4`

The gate did not self-terminate within the short review window and was interrupted fail-closed. The output directory remained empty because the gate script was interrupted before it wrote its report bundle.

However, the underlying provider jobs and databases were inspected directly.

### What the live evidence now shows

- The earlier `wait`-side `GeminiConversationThreadMismatch` jobs still exist as historical blockers:
  - `af24cd6c140943adbb5e2e20d7ad99c5`
  - `722a29272d0743c4bdc912829bafbafe`
- The new live send attempt in this batch produced job:
  - `8276d9afe7864619ac10e27a6171259f`
- That job ended as:
  - `status=error`
  - `phase=send`
  - `last_error_type=MaxAttemptsExceeded`
  - `last_error=Reached max_attempts=4 while retrying (cooldown): RuntimeError: <RuntimeError: empty error> [guard=retryable_extension_limit_reached:1/1]`
- Its idempotency row remained blank and unsent inside the same runtime instance:
  - `status=in_progress`
  - `sent=0`
  - `conversation_url=None`
  - `result_json=None`
  - `error=None`

## Independent Judgment

This batch is a valid, narrow hardening change, but it does **not** prove W1 live completion is fixed.

What it does prove:

- the retry scope is now constrained to explicit `BrowserContext.new_page` / `context.new_page` bootstrap only
- the local retry can happen at most once per `_open_gemini_page()` call
- restart/fallback semantics are preserved by regression tests
- retry-after-fresh-attach still respects reuse-enabled existing Gemini tabs
- we did not broaden retry behavior to `goto` or generic `*.new_page` strings

What it does **not** prove:

- that the OpenClawBot live Gemini send path is now green
- that the current `empty error` / blank same-runtime idempotency wedge is resolved

## Result

- Code batch verdict: `good narrow hardening`
- W1 live-status verdict: `still blocked`
- Next most likely blocker after this batch: same-runtime blank unsent idempotency replay / send-side silent failure handling
