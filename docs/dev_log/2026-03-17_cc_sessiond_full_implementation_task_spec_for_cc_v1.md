# CC-Sessiond Full Implementation Task Spec For Claude Code v1

Date: 2026-03-17

## Mission

Take the current `cc-sessiond` scaffold to a merge-ready full implementation.

This is not a greenfield prototype task. It is a convergence task:

- repair the broken scaffold
- align it with existing `CcExecutor` / `CcNativeExecutor`
- add a real backend adapter layer
- make lifecycle, continue, cancel, wait, and artifacts real
- add direct tests that prove the surface actually works

## Mandatory Reading Order

1. `AGENTS.md`
2. `docs/2026-03-17_claude_agent_sdk_session_manager_assessment_v1.md`
3. `docs/dev_log/2026-03-17_claude_agent_sdk_minimax_backend_probe_v1.md`
4. `docs/2026-03-17_cc_sessiond_full_implementation_blueprint_v1.md`
5. Inspect current scaffold commit `bae1ea1`

## Hard Constraints

- Use GitNexus before editing symbols
- Commit every meaningful slice
- Do not touch unrelated dirty files
- Do not revert user changes
- Keep compatibility-first semantics
- Write a walkthrough doc with `_v1.md`
- Run closeout before finishing

## Required Deliverables

### Deliverable 1: Repair Existing Scaffold

Must fix:

- wrong route import path
- router not mounted in `create_app()`
- scheduler loop not started
- sync cancel inside async routes
- `wait(timeout)` ignoring timeout
- missing dependency declaration

### Deliverable 2: Backend Adapter Layer

Add a backend abstraction under `chatgptrest/kernel/cc_sessiond/`:

- `base.py` or equivalent protocol
- `backend_sdk.py`
- `backend_cc_executor.py`
- optional placeholder `backend_cc_native.py`

Do not embed backend-specific logic directly in routes.

### Deliverable 3: Real Continue And Cancel Semantics

Must implement:

- parent session tracking
- continue mode semantics
- backend run id persistence
- async cancellation
- cancellation propagation to queued/running backend work

### Deliverable 4: Artifact And Event Discipline

Must persist:

- request
- status
- result
- error
- NDJSON events
- backend meta

Recommended root:

- `artifacts/cc_sessions/<session_id>/...`

### Deliverable 5: Direct Test Coverage

Add tests for:

- route import
- app registration
- create -> run -> complete flow
- create -> cancel flow
- continue flow
- wait timeout
- result retrieval
- events retrieval and/or stream
- backend adapter normalization
- dependency import smoke

## Batch Plan

### Batch A: Foundations

Files likely involved:

- `chatgptrest/api/app.py`
- `chatgptrest/api/routes_cc_sessiond.py`
- `chatgptrest/kernel/cc_sessiond/__init__.py`
- `chatgptrest/kernel/cc_sessiond/client.py`
- `pyproject.toml`
- `uv.lock`
- tests for startup/import

Expected outcome:

- app starts
- route imports cleanly
- routes are visible
- scheduler starts and stops with app lifecycle

### Batch B: Backend Adapters

Files likely involved:

- `chatgptrest/kernel/cc_sessiond/client.py`
- new backend adapter modules
- `chatgptrest/kernel/cc_executor.py`
- maybe `chatgptrest/kernel/cc_native.py` only for adapter touch points

Expected outcome:

- service can dispatch via `sdk_official`
- service can fallback to `cc_executor_headless`
- result contract normalized

### Batch C: Continue / Cancel / Wait

Files likely involved:

- session registry
- scheduler
- client
- routes
- direct integration tests

Expected outcome:

- continue semantics real, not fake options passthrough
- async cancel works
- wait timeout deterministic

### Batch D: Artifacts / Events / Docs

Files likely involved:

- `events.py`
- artifact helpers under `cc_sessiond`
- routes
- docs / contract docs / walkthrough

Expected outcome:

- session artifacts complete
- tailable events and session status match disk state

## Suggested Test Matrix

Minimum commands to actually run:

```bash
./.venv/bin/pytest -q tests/test_cc_sessiond.py
./.venv/bin/pytest -q tests/test_api_startup_smoke.py
./.venv/bin/pytest -q tests/test_cc_executor.py
./.venv/bin/pytest -q tests/test_advisor_runtime.py
```

Also add and run direct new tests if split out, for example:

```bash
./.venv/bin/pytest -q tests/test_cc_sessiond_routes.py
./.venv/bin/pytest -q tests/test_cc_sessiond_integration.py
```

If runtime wiring touches advisor bootstrap, also run:

```bash
./.venv/bin/pytest -q tests/test_advisor_v3_end_to_end.py
```

## Required Review Standard

You are not done when tests are green but only unit-level fake tests exist.

You are done only when:

- the route can import
- the app includes the route
- session state can transition beyond `pending`
- cancel works from async route context
- continue is not fake
- the dependency story is reproducible

## Required Final Output

Return JSON only:

```json
{
  "status": "succeeded" | "blocked" | "failed",
  "branch": "your-branch-name",
  "summary": "short summary",
  "commits": ["sha subject", "..."],
  "tests": [
    {"command": "pytest ...", "status": "passed|failed|not_run", "details": "short note"}
  ],
  "walkthrough_path": "absolute path or empty string",
  "changed_files": ["path", "..."],
  "residual_risks": ["...", "..."],
  "notes": ["...", "..."]
}
```
