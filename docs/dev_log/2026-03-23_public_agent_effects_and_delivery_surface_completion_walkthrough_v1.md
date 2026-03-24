# 2026-03-23 Public Agent Effects And Delivery Surface Completion Walkthrough v1

## Why This Package Existed

`public-agent-contract-first-upgrade` had already landed on the live public surface, but the northbound delivery model was still fragmented:

- turn responses had `status + next_action`
- session/status responses had a different shape
- deferred accept responses were race-prone
- workspace action semantics were still partly hidden inside `control_plane`
- wrapper `--out-summary` in agent/public-MCP mode did not actually persist anything useful

That was enough for experimentation, but not enough for launch-ready coding-agent integration.

## What Changed

### 1. Centralized northbound lifecycle and delivery projection

Added shared helpers in [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py) to build:

- `lifecycle.phase`
  - `accepted`
  - `clarify_required`
  - `progress`
  - `completed`
  - `failed`
  - `cancelled`
- `delivery`
  - `mode`
  - `stream_url`
  - `answer_chars`
  - `accepted`
  - `answer_ready`
  - `watchable`
  - `artifact_count`
  - `terminal`
- `effects`
  - `artifact_delivery`
  - `workspace_action` when applicable

These helpers are now applied at the shared exits:

- `_build_agent_response(...)`
- `_augment_agent_response(...)`
- `_session_response(...)`
- deferred accept responses
- cancel response

### 2. Removed deferred accept race

Previously the `202 deferred` response was built after the background thread started.
If the background task completed fast enough, the accept response could already look terminal.

This package fixes that by snapshotting the accepted response before the background thread mutates the session.

### 3. Made workspace effect surface explicit

Workspace clarify and workspace completion responses now explicitly project:

- `workspace_request`
- `workspace_result`
- `workspace_diagnostics`
- `effects.workspace_action`

This makes the workspace path machine-readable without forcing clients to decode nested control-plane internals.

### 4. Fixed wrapper summary persistence

In [chatgptrest_call.py](/vol1/1000/projects/ChatgptREST/skills-src/chatgptrest-call/scripts/chatgptrest_call.py), agent/public-MCP success no longer returns before writing `--out-summary`.

The wrapper now writes a structured summary containing:

- `mode=agent_public_mcp`
- `session_id`
- `route`
- `lifecycle`
- `delivery`
- `effects`
- `result` (full raw response)

## Verification

### Deterministic tests

Passed:

```bash
./.venv/bin/pytest -q \
  tests/test_routes_agent_v3.py \
  tests/test_skill_chatgptrest_call.py \
  tests/test_public_agent_effects_delivery_validation.py
```

### Static compile check

Passed:

```bash
python3 -m py_compile \
  chatgptrest/api/routes_agent_v3.py \
  skills-src/chatgptrest-call/scripts/chatgptrest_call.py \
  chatgptrest/eval/public_agent_effects_delivery_validation.py \
  ops/run_public_agent_effects_delivery_validation.py \
  tests/test_routes_agent_v3.py \
  tests/test_skill_chatgptrest_call.py \
  tests/test_public_agent_effects_delivery_validation.py
```

### Live validation

Passed:

```bash
PYTHONPATH=. ./.venv/bin/python ops/run_public_agent_effects_delivery_validation.py
```

Accepted artifact:
- [report_v1.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/public_agent_effects_delivery_validation_20260323/report_v1.json)

### Adjacent regression checks

Still green after this package:

```bash
PYTHONPATH=. ./.venv/bin/python ops/run_public_agent_live_cutover_validation.py
PYTHONPATH=. ./.venv/bin/python ops/run_public_agent_mcp_validation.py
```

## Final State

This package closes the northbound lifecycle/effects/delivery gap for launch-scoped public-agent use.

What is now true:
- clients no longer need to infer state from `status + next_action` alone
- deferred accept is stable
- wrapper summary files are usable again
- workspace actions expose a real effect surface

What is still intentionally outside this package:
- external provider completion proof
- full-stack deployment proof
- heavy execution lane approval
