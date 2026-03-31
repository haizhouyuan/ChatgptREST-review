# 2026-03-17 cc-sessiond SDK Runtime Enablement And Fix Walkthrough v1

## Summary

This round completed the missing runtime work for `cc-sessiond` on
`feat/public-advisor-agent-facade`:

- corrected the official SDK package/module name
- repaired legacy SQLite migration ordering
- fixed `CcExecutor` result normalization
- fixed continuation semantics to resume the real Claude session id
- installed the official SDK into the shared project `.venv`
- updated `uv.lock` so the environment can be reproduced

## Root Cause

The branch had two separate problems mixed together:

1. The dependency was named incorrectly.
   - branch code referenced `claude-agent-sdk` / `claude_agent_sdk`
   - the official Python package is `claude-code-sdk`
   - the importable module is `claude_code_sdk`

2. Even after fallback-to-`CcExecutor` was added, the execution path still had
   real runtime bugs:
   - legacy DB migration created an index before adding new columns
   - `continue_run()` passed a single `CcTask` into `dispatch_conversation()`
   - `CcExecutorBackend` read non-existent `CcResult` fields such as
     `output_text`, `total_cost_usd`, `total_tokens`, and `turns`
   - the client never persisted the true backend session id needed for resume

## Code Changes

### 1. Dependency correction

- changed `pyproject.toml` from `claude-agent-sdk>=0.1,<1`
  to `claude-code-sdk>=0.0.25,<1`
- regenerated `uv.lock`

### 2. SDK backend repair

`chatgptrest/kernel/cc_sessiond/backends/backend_sdk.py`

- switched to `from claude_code_sdk import query, ClaudeCodeOptions, ResultMessage`
- moved MiniMax routing into `ClaudeCodeOptions.env`
- used the official call shape:

```python
async for message in query(prompt=prompt, options=sdk_options):
    ...
```

- implemented continuation using:
  - `resume=<backend_run_id>`
  - `continue_conversation=True`

### 3. CcExecutor backend repair

`chatgptrest/kernel/cc_sessiond/backends/backend_cc_executor.py`

- normalized real `CcResult` fields:
  - `output`
  - `cost_usd`
  - `input_tokens`
  - `output_tokens`
  - `num_turns`
  - `session_id`
- `continue_run()` now resumes with `dispatch_headless()` using
  `task.stateless = False` and `task.session_id = <parent backend_run_id>`
- added `backend_run_id` to emitted completion events

### 4. Client/backend state repair

`chatgptrest/kernel/cc_sessiond/client.py`

- stored backend metadata earlier in execution
- refused continuation when parent session has no `backend_run_id`
- updated registry/backend artifact metadata when backend events include the real
  run/session id
- treated `subtype=failed|error` as failed session state instead of completed
- appended backend events to artifact storage

### 5. Legacy schema migration repair

`chatgptrest/kernel/cc_sessiond/registry.py`

- moved `_migrate()` before index creation so old DBs can be upgraded safely

## Installation And Runtime Notes

The shared project interpreter is:

- `/vol1/1000/projects/ChatgptREST/.venv`

Actual install command used:

```bash
cd /vol1/1000/projects/ChatgptREST
./.venv/bin/pip install claude-code-sdk
```

Lock/update commands used from the feature worktree:

```bash
cd /vol1/1000/worktrees/chatgptrest-advisor-agent-facade-20260317
uv lock
uv sync --python /vol1/1000/projects/ChatgptREST/.venv/bin/python
uv sync --python /vol1/1000/projects/ChatgptREST/.venv/bin/python --all-extras
```

Important note:

- `uv sync` without extras trimmed the shared `.venv` down to the minimal
  dependency set from `pyproject.toml`
- `uv sync --all-extras` was then run immediately to restore the full shared
  development/test environment

Current environment check:

- `claude_code_sdk` imports successfully
- `claude_agent_sdk` is absent, as expected

## Validation

Direct runtime probes:

- legacy schema migration now succeeds
- `CcExecutorBackend.continue_run()` now resumes with the parent Claude session id
- live `POST /v1/cc-sessions` probe now writes:
  - `request.json`
  - `status.json`
  - `backend_meta.json`

Tests run:

```bash
./.venv/bin/pytest -q tests/test_cc_sessiond.py
./.venv/bin/pytest -q tests/test_cc_sessiond_routes.py tests/test_api_startup_smoke.py
./.venv/bin/pytest -q tests/test_cc_executor.py
./.venv/bin/pytest -q tests/test_cc_sessiond.py tests/test_cc_sessiond_routes.py tests/test_api_startup_smoke.py tests/test_cc_executor.py
```

## Residual Risk

- `SDKBackend` is now wired to the official package, but it still lacks a
  real end-to-end prompt execution validation against a live MiniMax-backed
  Claude Code session
- cancellation is still cooperative for `CcExecutor`; there is no underlying
  hard stop primitive yet
- the GitNexus index did not resolve these new `cc_sessiond` symbols from the
  feature worktree, so worktree-local `git diff` was used as the authoritative
  scope check for this slice
