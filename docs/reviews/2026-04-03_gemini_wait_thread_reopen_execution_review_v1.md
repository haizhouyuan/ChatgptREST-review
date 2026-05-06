# 2026-04-03 Gemini Wait Thread Reopen Execution Review v1

## 1. Scope

This review freezes the latest execution batch around the live `OpenClawBot -> /v3/agent/turn -> gemini_web.ask` planning path.

The batch focus is narrow:

1. remove wrong-thread false success
2. keep fail-closed semantics
3. add one controlled same-session repair layer when Gemini repeatedly falls back to `/app`

## 2. What This Batch Actually Changes

### 2.1 Provider-side Gemini hardening kept in scope

The batch keeps these already-proven local improvements:

1. Drive picker handling is more robust across consent, popup, iframe, and debug surfaces
2. anchor-only Gemini transcript chrome is stripped more safely
3. broad `accounts.google.com` hops are no longer blindly treated as login failure

### 2.2 Wait-side thread retention hardening

`chatgpt_web_mcp/providers/gemini/wait.py` now does all of the following when a concrete requested Gemini thread URL is known:

1. exact requested `cid` is preferred over title match
2. wrong-thread rebound remains fail-closed
3. direct reopen of the requested concrete thread is attempted
4. loop-level reopen is attempted again if the page falls back to `/app`
5. after that reopen budget is exhausted, one controlled same-session repair attempt is allowed

That new same-session repair is still bounded:

- it reuses the requested concrete thread as authority
- it does not allow rebinding onto another thread
- it still fails closed if the requested thread does not stabilize

## 3. What Was Validated

### 3.1 Focused automated checks

The current batch is validated by focused local tests, including:

1. `tests/test_gemini_wait_sidebar_thread_guard.py`
2. `tests/test_gemini_mode_selector_resilience.py`
3. `tests/test_gemini_drive_picker_resilience.py`
4. `tests/test_openclawbot_planning_task_plane_live_completion_gate.py`
5. `tests/test_gemini_wait_conversation_hint.py`
6. `tests/test_gemini_wait_conversation_url_upgrade.py`

### 3.2 What is proven vs not proven

This batch proves:

1. local wait logic no longer silently accepts older wrong-thread content
2. requested-thread reopen now has one more controlled recovery layer
3. the next recovery step is still constrained by fail-closed semantics

This batch does **not** yet prove:

1. that live Gemini completion is green
2. that the page will now always remain on the requested thread
3. that compact planning next-step routing is fully proven end-to-end in live request serialization
4. that MCP transport timeout behavior should be broadened for all JSON-RPC traffic

## 4. Current Independent Judgment

My current independent judgment is:

1. the dominant local wrong-thread bug has been materially reduced
2. the remaining front blocker is still a live Gemini thread-persistence problem
3. one additional bounded same-session repair attempt path is justified
4. broader MCP timeout semantics should not be claimed solved in this batch

## 5. One-Line Conclusion

> This batch should be read as: local Gemini wait recovery is now stricter and one layer deeper, but live thread persistence is still the front blocker and the batch should not overclaim transport or compact-lane success.
