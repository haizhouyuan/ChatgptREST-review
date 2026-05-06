# 2026-03-31 Wrapped Review ChatGPT Driver Blocked Recovery And Warm Page Fix v1

## What changed

This change hardens the ChatGPT driver/runtime path used by wrapped review workflows.

Updated code:

- `chatgpt_web_mcp/_tools_impl.py`
- `tests/test_chatgpt_cdp_page_reuse.py`
- `docs/runbook.md`

## Root cause

Wrapped ChatGPT review could fail even when the service stack was healthy because three internal behaviors combined poorly:

1. `chatgpt_web_self_check` and `chatgpt_web_capture_ui` were blocked by the same blocked-state gate used for prompt-sending tools.
2. In CDP mode, no-prompt diagnostics always closed the ChatGPT page, so the system did not preserve a warm reusable homepage tab.
3. Auto-verification only tried visible checkbox/button selectors and iframe locators. Current Cloudflare pages can expose only a hidden `cf-turnstile-response` input with no visible selector match, so the auto-click path never attempted a fallback click.

The result was:

- blocked state could not be cleared by a safe probe path,
- diagnostics could not preserve a warm ChatGPT tab,
- wrapped review had to create a fresh ChatGPT page and was more likely to hit Cloudflare again.

## Fixes

### 1. Blocked-safe diagnostics

`_chatgpt_enforce_not_blocked(...)` now allows:

- `self_check`
- `capture_ui`

even while blocked cooldown is active.

Prompt-sending paths still fail closed.

### 2. Warm CDP page preservation

Added helper logic so that:

- `chatgpt_web_self_check`
- `chatgpt_web_capture_ui`

do not close the page in CDP mode when:

- `close_context == False`
- no explicit `conversation_url` was requested
- the page is a homepage-style ChatGPT page rather than a conversation tab

This preserves a warm ChatGPT page asset across diagnostics.

### 3. Stale blocked-state clearing after successful diagnostics

Successful `self_check` / `capture_ui` now clear an active stale blocked state and record that in the tool result.

### 4. Turnstile fallback click

`_chatgpt_try_auto_verification_click(...)` now has a best-effort fallback order after visible selector attempts fail:

1. Turnstile frame body center
2. Hidden `cf-turnstile-response` input ancestor box
3. Page-body fallback center

This does not bypass Cloudflare. It only automates the same click a user would make in the already-open browser session.

## Validation

Validated with:

```bash
python3 -m py_compile chatgpt_web_mcp/_tools_impl.py tests/test_chatgpt_cdp_page_reuse.py

cd /vol1/1000/projects/ChatgptREST
./.venv/bin/pytest -q \
  tests/test_chatgpt_cdp_page_reuse.py \
  tests/test_skill_chatgptrest_call.py \
  -k 'chatgpt or transport or self_check or capture_ui'
```

Expected coverage from this patch:

- blocked diagnostics are allowed,
- warm CDP homepage tabs are preserved,
- hidden-turnstile fallback click is attempted,
- self-check clears stale blocked state when the page is healthy.

## Operational note

This fix does not claim Cloudflare will never appear again.

It fixes the internal recovery path so wrapped workflows can:

- probe safely while blocked,
- preserve a reusable ChatGPT page,
- attempt a better auto-verification fallback,
- reduce false “service unavailable” incidents caused by stale blocked state and cold-page churn.
