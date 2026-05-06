# 2026-03-25 Public Agent Wrapper Sync Summary Fix v1

## Context

After the wrapper handoff fixes in `74dc247` / `75ff09d`, live client retest confirmed that:

- `ISSUE-0020` was fixed
- the deferred handoff part of `ISSUE-0021` was materially improved

But a narrower sync-path regression remained:

- `ISSUE-0022`
- sync planning-style requests could create `out-summary` quickly and leave it stuck at:
  - `status=initialized`
  - `submission_stage=initialized`
  - `submission_started=false`

even while the wrapper process was already inside the real `advisor_agent_turn` call.

## Root cause

`chatgptrest_call.py` wrote an early snapshot after MCP `initialize`, but did not write another pre-turn snapshot immediately before the blocking `advisor_agent_turn` call on sync paths.

That left a time window where the client-visible summary exposed raw MCP bootstrap state instead of real turn-submission state.

## Fix

- `skills-src/chatgptrest-call/scripts/chatgptrest_call.py`
  - Added a second early summary write immediately before entering `advisor_agent_turn`.
  - Synthesized runtime-only summary fields so pre-result snapshots now show:
    - `status=submitted`
    - `result.status=submitted`
    - `requested_runtime.submission_stage=submit_turn`
    - `requested_runtime.submission_started=true`
    - `lifecycle.phase=progress`
  - Kept bootstrap snapshots for the earlier MCP initialize phase, but they are no longer the last visible state once the wrapper has actually started submitting the turn.

## Verification

- `./.venv/bin/python -m py_compile skills-src/chatgptrest-call/scripts/chatgptrest_call.py`
- `./.venv/bin/pytest -q tests/test_skill_chatgptrest_call.py`

New regression coverage:

- `test_skill_main_agent_mode_sync_summary_advances_past_initialize`

This test reads `out-summary` inside the fake `advisor_agent_turn` call and asserts that the summary already moved beyond bootstrap before the blocking turn execution begins.
