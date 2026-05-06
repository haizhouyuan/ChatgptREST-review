# 2026-03-09 Gemini UI Prompt Box Stability Fix

## Summary

Gemini send-path instability on 2026-03-09 was a compound runtime bug:

1. shared CDP Chrome tabs were reused across multiple Gemini worker processes
2. Gemini new chat briefly exposed a transient `textarea` before switching to the stable rich editor
3. the driver could grab and click that transient `textarea`, then stall on `Locator.click ... waiting for locator("textarea").first`

The production fix narrows both failure surfaces:

- default Gemini CDP behavior now opens a fresh tab per invocation
- prompt box detection now prefers stable rich-editor selectors and only falls back to `textarea` after a short grace window
- send paths now focus the prompt box through a shared helper instead of raw `prompt_box.click()`

## Root Cause

### 1. Shared CDP tab reuse across processes

Gemini jobs were running through shared local Chrome, but lock protection was only process-local. Reusing an existing `gemini.google.com` tab let one worker mutate or close another worker's page.

Observed symptom:

- `Target page, context or browser has been closed`

This was a concurrency bug in the driver/browser contract, not a model error.

### 2. Transient textarea bootstrap

Gemini new chat did not present a stable editor immediately. The live DOM sequence was:

- initial bootstrap: visible `textarea`
- after roughly 1 to 2 seconds: stable editor appears as `div[role='textbox']` / `div.ql-editor[contenteditable]` / `input-area-v2`

The old path treated the transient `textarea` as a normal prompt box and clicked it too early.

Observed symptom:

- `UiTransientError: Locator.click: Timeout 30000ms exceeded. Call log: - waiting for locator("textarea").first`

## Code Changes

### `chatgpt_web_mcp/providers/gemini/core.py`

- Added `GEMINI_REUSE_EXISTING_CDP_PAGE` gate and made isolated-tab mode the default.
- Added `GEMINI_TEXTAREA_FALLBACK_GRACE_SECONDS` with default `1.8`.
- Updated `_gemini_find_prompt_box()` to prefer:
  - `div[role='textbox']`
  - `div.ql-editor[contenteditable='true']`
  - `input-area-v2`
  - delayed `textarea` fallback
- Added `_gemini_focus_prompt_box()` so send-path callers focus the live editor through one shared stabilization helper.

### `chatgpt_web_mcp/providers/gemini/ask.py`

- Replaced raw prompt-box clicks with `_gemini_focus_prompt_box()` in:
  - `gemini_web_ask`
  - `gemini_web_ask_pro`
  - `gemini_web_ask_pro_thinking`
  - `gemini_web_ask_pro_deep_think`
  - deep-think new-conversation sender

### `chatgpt_web_mcp/providers/gemini/generate_image.py`

- Aligned image-generation prompt entry with the same prompt-box focus helper.

### Tests

Added coverage in `tests/test_gemini_cdp_page_isolation.py` for:

- fresh CDP tab by default
- opt-in reuse path
- rich textbox preferred over transient textarea
- grace-window wait before textarea fallback

## Live Validation

### Reproduction before final fix

Fresh Gemini smoke still failed after the first half-fix, proving shared-tab isolation alone was insufficient:

- `c5610da7c9674135812cc6019aab9696`
- `a3da3533c1b0489caf14e2700443c066`

Failure shape:

- `UiTransientError`
- `Locator.click ... locator("textarea").first`

### DOM probe

Live Chrome probe showed the settled prompt editor was the rich textbox, not textarea:

- `div.ql-editor[contenteditable][role='textbox']`

Transition probe showed the bootstrap order:

- immediate new chat: transient `textarea`
- about 1.4s later: stable rich editor

### Final direct interaction probe

After the focus-helper patch, direct live interaction succeeded:

- focused stable `div.ql-editor ... role="textbox"`
- typed successfully

### Final end-to-end live test

Human-language prompt:

- `请用三句话说明为什么程序员要写回归测试。`

Job:

- `2cfdf138a9e24b0aaf72bc3c75b3272f`

Result:

- `status=completed`
- answer written successfully
- no prompt-box failure

## Operational Guidance

- If Gemini region is blocked, fix egress first and restart Chrome.
- If Gemini fails with `locator("textarea").first`, treat it as prompt-box bootstrap drift.
- Do not opt back into shared-tab reuse unless you have a specific reason and single-worker discipline.

## Outcome

This fix converts Gemini prompt entry from a race-prone UI guess into a stabilized two-part contract:

1. isolated CDP tab ownership by default
2. stable-editor-first prompt focus

That is the root fix for the 2026-03-09 Gemini UI send instability.
