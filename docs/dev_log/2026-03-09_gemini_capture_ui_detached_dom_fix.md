# 2026-03-09 Gemini Capture UI Detached-DOM Fix

## Scope

This follow-up closes the remaining technical part of GitHub issue `#107`:

- `gemini_web_capture_ui` could fail to capture `composer_prompt`
- failure shape: `Locator.screenshot: Element is not attached to the DOM`

The doc-ownership part of `#107` is separate and stays isolated from this code fix.

## Root Cause

`gemini_web_capture_ui` used `_gemini_find_prompt_box()` and then directly passed that locator into `_ui_screenshot()`.

Gemini's composer bootstrap is not stable during the first render window:

- the transient node can be found
- then replaced by the stable rich editor
- then the screenshot call hits a detached element

That is the same DOM replacement class as the earlier Gemini send-path instability, but on the capture-only lane.

## Code Fix

Changed `chatgpt_web_mcp/providers/gemini/capture_ui.py`:

- imported `_gemini_focus_prompt_box()`
- added `_looks_like_detached_dom_capture()`
- added `_capture_composer_prompt()`
  - focus the stable editor first
  - if screenshot fails with detached-DOM wording, reacquire prompt box and retry once

This keeps the fix Gemini-local and avoids widening scope into the shared screenshot helper.

## Tests

Added `tests/test_gemini_capture_ui.py`:

- detached-DOM error classification
- retry path for `composer_prompt` screenshot

## Live Validation

Live no-prompt capture run:

- command used `CHATGPT_CDP_URL=http://127.0.0.1:9226`
- target conversation: `https://gemini.google.com/app/8e354f302527695e`
- run id: `gemini_web_capture_ui:20260309_101707:46481d8c773e`
- output dir: `tmp/gemini_capture_ui_smoke`

Observed result:

- `status=completed`
- `composer_prompt.png` captured successfully
- `manifest.json` written

Relevant targets:

- `page_full.png`
- `composer_prompt.png`
- `model_selector_button.png`

`send_button` and `tools_button` were `NotVisible` in that settled conversation view, but that is expected state-specific evidence, not a capture failure.

## Outcome

The composer capture instability in `#107` is fixed.

Remaining `#107` concern that is not addressed by this code change:

- whether `docs/gemini_web_ui_reference.md` should stay as a tracked generated document and what its ownership/commit policy should be
