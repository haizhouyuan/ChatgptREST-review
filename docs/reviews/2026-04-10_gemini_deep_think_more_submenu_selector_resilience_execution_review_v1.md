# Gemini Deep Think More Submenu Selector Resilience — Execution Review v1

Date: 2026-04-10

## Trigger

GeminiDT invocations through `gemini_web.ask` were intermittently failing even though the account/operator confirmed the `Deep Think` capability was still present in Gemini Web.

Manual UI verification showed a concrete surface drift:

- older flow: prompt-area add/tools menu opened by the `+` button showed `Deep Think` directly
- current flow: the first-layer menu no longer shows `Deep Think`; the operator must click `More / 更多` to reveal the second-layer entry

## Root Cause

The existing Gemini web automation already supported a folded prompt-area menu trigger, but tool discovery stopped at the first visible overlay layer.

Affected behavior:

- `_gemini_open_tools_drawer()` could open the add/tools surface
- `_gemini_find_tool_item()` only searched the currently visible first-layer tool/menu items
- `gemini_web_self_check()` enumerated only that first layer when deciding whether `Deep Think` was visible

As a result, current UIs that fold `Deep Think` under a second-level `More / 更多` submenu were misclassified as:

- tool missing
- UI drift
- or entitlement/quota ambiguity

when the tool was actually present in the next layer.

## Changes

Code:

- added `_GEMINI_TOOLS_MORE_RE` to normalize `More / 更多 / More tools / 更多工具` submenu variants
- added `_gemini_expand_more_tools_submenu()` in `chatgpt_web_mcp/providers/gemini/core.py`
- updated `_gemini_find_tool_item()` to expand the second-level submenu once before concluding the tool is absent
- updated `gemini_web_self_check()` to enumerate submenu entries when `Deep Think` is not present in the first-layer menu

Tests:

- added selector coverage for `_gemini_expand_more_tools_submenu()` in `tests/test_gemini_tools_menu_selectors.py`
- added behavior coverage for folded-menu discovery in `tests/test_gemini_mode_selector_resilience.py`

Docs:

- updated `GEMINI.md` to record that GeminiDT may require probing a second-level `More / 更多` submenu

## Operational Result

The system now distinguishes between:

- true tool absence
- account/quota gating
- and prompt-area submenu folding

This does not solve every GeminiDT failure mode. It specifically fixes the known UI drift where `Deep Think` moved from the first prompt-area tool layer into a `More / 更多` submenu.

## Remaining Gaps

- Google can still move `Deep Think` from menu semantics to a dedicated prompt-bar control; that would require another selector update
- `needs_followup / same_session_repair` behavior in advisor-agent delivery remains a separate product/runtime issue
- entitlement/quota gating can still hide the control entirely, and that should remain a distinct diagnosis from selector drift
