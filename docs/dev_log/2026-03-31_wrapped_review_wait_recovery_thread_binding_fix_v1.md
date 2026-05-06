# 2026-03-31 Wrapped Review Wait Recovery Thread Binding Fix v1

## Problem

The packaged ChatGPT Pro review lane no longer failed at prompt submission, but the first wrapped
review still fell into `cooldown` during the long-answer wait/export path.

Observed incident:

- job: `4f156f66caae472a89464742c3768bd8`
- conversation: `https://chatgpt.com/c/69cb1ba2-0284-83a8-9291-003e5c03ed8d`
- result: `status=cooldown`, `error_type=Blocked`, `error=chatgptMCP blocked: cloudflare`
- blocked artifact title: `Just a moment...`
- blocked artifact URL: `https://chatgpt.com/`

The key mismatch was:

- the wrapped review already had a valid `conversation_url`
- recovery logic in `chatgpt_web_ask` / `chatgpt_web_wait` still used `_chatgpt_refresh_page(page, ...)`
- `_chatgpt_refresh_page()` only did `page.reload()` on the current page
- when the current page had drifted back to the ChatGPT root, timeout recovery refreshed the root
  page instead of returning to the known thread URL
- that root refresh could trigger Cloudflare and poison the whole wrapped review job

## Fix

### 1. Thread-aware refresh recovery

`chatgpt_web_mcp/_tools_impl.py`

- `_chatgpt_refresh_page()` now accepts `preferred_url`
- when `preferred_url` is a known thread URL and the current page is not already that thread, the
  recovery path navigates back to the thread instead of blindly reloading the current page
- fallback navigation also now prefers `preferred_url` over the current/root URL

### 2. Pass thread URL through all critical ChatGPT recovery branches

The following recovery paths now pass `conversation_url_effective or conversation_url` as
`preferred_url`:

- ask timeout recovery (`ask_timeout_wait_start`)
- ask transient Playwright recovery (`ask_wait_answer`)
- ask transient assistant-error recovery (`ask_transient_assistant_error`)
- wait timeout recovery (`wait_timeout`)
- wait transient Playwright recovery (`wait_error`)
- wait transient assistant-error recovery (`wait_transient_assistant_error`)
- explicit `chatgpt_web_refresh(conversation_url=...)`
- upload-surface recovery in the ask path

This change intentionally keeps the blast radius inside the ChatGPT web tool lane and does not
modify Gemini/Qwen/provider routing.

## Tests

Added/updated:

- `tests/test_chatgpt_cdp_page_reuse.py`

New coverage:

1. if current page is `https://chatgpt.com/` but recovery knows the thread URL, refresh recovery
   must navigate back to the thread instead of reloading root
2. if current page is already on the same thread, refresh recovery keeps the cheaper `reload()`
   path

Regression suites run:

```bash
./.venv/bin/pytest -q tests/test_chatgpt_cdp_page_reuse.py tests/test_gemini_mode_selector_resilience.py tests/test_skill_chatgptrest_call.py
./.venv/bin/pytest -q tests/test_executor_pro_fallback.py tests/test_chatgpt_web_answer_rehydration.py tests/test_mcp_unified_ask_min_chars.py
python3 -m py_compile chatgpt_web_mcp/_tools_impl.py
```

All passed.

## Expected operator effect

For wrapped long reviews and other long ChatGPT jobs:

- when the job already has a valid thread URL, timeout recovery stays bound to that thread
- the recovery path no longer refreshes the ChatGPT home/root page by default
- this removes the specific failure mode where the packaged review lane succeeds at prompt send but
  later drops into a root-page Cloudflare block during wait/export recovery

## Boundaries

- This does not claim ChatGPT Web will never hit external Cloudflare again.
- It fixes the internal recovery bug that made the packaged review lane re-enter the root page even
  after a thread URL was already known.
- The next required validation step is live rerun of the wrapped review workflow itself.
