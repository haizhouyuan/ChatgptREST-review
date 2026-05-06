## Summary

This tranche decoupled the coding-agent executor runtime budget from the foreground turn wait budget.

Before this fix, formal controller-backed `coding_agent` runs passed the same `timeout_seconds`
value into the executor subprocess. That made slow Claude-family executors fail as hard
`FAILED` runs after 300 seconds, even when the formal session itself was already operating in
background/deferred mode.

The new behavior is:

- the public turn may still return quickly in deferred mode;
- the background coding-agent subprocess gets an executor-family-aware runtime budget;
- timeout failures now always persist a `result.json`, `stderr.txt`, and elapsed timing
  evidence instead of leaving an empty artifact directory.

## Code Changes

Files changed:

- `chatgptrest/controller/coding_agent_executor.py`
- `tests/test_coding_agent_executor.py`

Implemented changes:

1. Added executor-family timeout floors:
   - `claude` family defaults to `900s`
   - `codex` family defaults to `300s`
2. Added env overrides:
   - `CHATGPTREST_CODING_AGENT_MIN_TIMEOUT_CLAUDE_SECONDS`
   - `CHATGPTREST_CODING_AGENT_MIN_TIMEOUT_CODEX_SECONDS`
3. Recorded both:
   - `requested_timeout_seconds`
   - `effective_timeout_seconds`
4. Caught `subprocess.TimeoutExpired` in Claude-wrapper mode and force-wrote:
   - `stdout.txt`
   - `stderr.txt`
   - `result.json`
5. Added regression coverage for:
   - family timeout floor application
   - timeout artifact persistence

## Why This Was Needed

Formal OpenClaw continuations had already proven that:

- executor discovery worked after the earlier PATH fix;
- structured output parsing worked after the Claude envelope fix;
- the remaining blocker was the controller-backed subprocess timeout.

The concrete failing run before this change was:

- session: `openclaw-real-closure-card-codex2-session-20260406a`
- run: `229d446fa03c40c99baaf45ccf78673f`

The controller DB showed the exact failure:

- `claudegac ... --effort medium ... timed out after 300 seconds`

That meant the formal path was still coupling "how long the API turn waits" with
"how long the executor is allowed to work".

## Validation

Local validation:

```bash
python3 -m py_compile chatgptrest/controller/coding_agent_executor.py
./.venv/bin/pytest -q tests/test_coding_agent_executor.py tests/test_controller_engine_planning_pack.py tests/test_routes_agent_v3.py
```

Observed result:

- compile passed
- targeted regression suite passed

Runtime evidence after the code change:

- timed-out formal run now wrote:
  - `artifacts/controller_coding_agent/f2e0419e2ebd49ad9ea58a2503e15cf9/result.json`
  - `artifacts/controller_coding_agent/f2e0419e2ebd49ad9ea58a2503e15cf9/stderr.txt`
- `result.json` explicitly recorded:
  - `requested_timeout_seconds=120`
  - `effective_timeout_seconds=900`
  - `error=executor_timeout_after_900s`

## Outcome

This fix did not magically make every executor/effort combination fast enough, but it did
remove the incorrect 300-second ceiling from the formal coding-agent lane and turned timeout
failures into durable, inspectable artifacts.

That narrowed the remaining product question from:

- "is the formal coding-agent lane broken?"

to:

- "which executor/effort combinations are actually practical for formal user closure?"
