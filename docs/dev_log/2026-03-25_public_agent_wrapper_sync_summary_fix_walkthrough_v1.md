# 2026-03-25 Public Agent Wrapper Sync Summary Fix Walkthrough v1

## Goal

Close `ISSUE-0022`: prevent sync-path `out-summary` from exposing a stale MCP-initialize snapshot while the wrapper is already blocked inside the real turn submission.

## Steps

1. Read the live client retest notes from `b0176d4`.
   - Confirmed the new issue was narrower than the earlier deferred-handoff bug.
   - Confirmed the bad state was specifically:
     - `status=initialized`
     - `submission_stage=initialized`
     - `submission_started=false`

2. Re-checked wrapper control flow.
   - The wrapper wrote one snapshot before MCP initialize.
   - Wrote another after initialize.
   - Then immediately entered blocking `advisor_agent_turn`.
   - There was no client-visible snapshot written at the “turn submission has started” boundary on sync paths.

3. Applied a narrow fix.
   - Before calling `advisor_agent_turn`, the wrapper now writes another runtime snapshot with:
     - `submission_stage=submit_turn`
     - `submission_started=true`
   - Runtime-only snapshots now synthesize user-facing fields (`status`, `lifecycle`, `delivery`) so they read like wrapper state, not raw MCP bootstrap internals.

4. Added regression coverage.
   - New test intercepts the fake `advisor_agent_turn` call and reads the on-disk summary at that exact moment.
   - The test asserts the summary already says `submitted`, not `initialized`.

5. Verified.
   - `./.venv/bin/python -m py_compile ...`
   - `./.venv/bin/pytest -q tests/test_skill_chatgptrest_call.py`

## Result

The deferred handoff behavior from `74dc247` remains intact, and sync planning-style calls now expose a truthful early summary once the turn submission has actually started.
