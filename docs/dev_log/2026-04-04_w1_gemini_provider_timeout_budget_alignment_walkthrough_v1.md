# 2026-04-04 W1 Gemini Provider Timeout Budget Alignment Walkthrough v1

## What I changed

I isolated one narrow provider-facing change for `W1`:

1. tighten the real timeout budget in `gemini_web_ask_pro`;
2. add targeted tests that prove timeout-path fail-closed behavior before send and before page-slot acquisition.

## Why I changed it

The previous batches had already removed:

1. send-worker clog from low-value Gemini repair jobs;
2. MCP HTTP fresh-session replay inflation.

But live evidence still showed:

1. blank Gemini timeout;
2. no thread URL;
3. repeated cooldown/error cycling.

That pointed at the provider path itself.

## How I kept scope narrow

I explicitly avoided bundling this batch with broader Gemini feature drift. The intent here is not to expand Gemini capability surface; it is to harden timeout/fail-closed behavior on the existing live path.

## What I verified

I ran:

1. `python3 -m py_compile chatgpt_web_mcp/providers/gemini/ask.py tests/test_gemini_provider_timeout_budget.py`
2. `./.venv/bin/pytest -q tests/test_gemini_provider_timeout_budget.py tests/test_openclawbot_planning_task_plane_live_completion_gate.py tests/test_run_openclawbot_planning_task_plane_live_completion_gate.py`

All passed.

## What this does not prove yet

It does not prove:

1. `W1` live completion is green;
2. Gemini answer quality is now sufficient;
3. ChatGPT live lane is ready.

It only proves the provider timeout budget slice is tighter and test-covered.
