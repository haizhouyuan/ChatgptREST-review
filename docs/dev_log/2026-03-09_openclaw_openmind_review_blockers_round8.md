# 2026-03-09 OpenClaw + OpenMind Review Blockers Round 8

## Goal

Close the next two external review blockers for the OpenClaw/OpenMind baseline:

1. make the public review branch self-contained for plugin installation
2. replace the inferred `sessions_spawn` / `subagents` proof with live negative runtime probes

## Changes

### 1. Public review mirror now includes plugin sources

Updated `ops/sync_review_repo.py` so the public review branch mirrors:

- `openclaw_extensions/openmind-advisor`
- `openclaw_extensions/openmind-graph`
- `openclaw_extensions/openmind-memory`
- `openclaw_extensions/openmind-telemetry`

This removes the remaining public reproducibility gap for `scripts/rebuild_openclaw_openmind_stack.py`, which installs OpenMind plugins from repo-local paths.

Added sync regression coverage in:

- `tests/test_sync_review_repo.py`

### 2. Removed residual `subagents` ambiguity from the rebuild baseline

The supported baseline no longer writes `subagents.allowAgents` for `main` in `ops` mode.

Reason:

- the intended communication model is `maintagent -> main` via `sessions_send`
- keeping a dormant `subagents.allowAgents=["maintagent"]` entry created unnecessary review ambiguity

Updated:

- `scripts/rebuild_openclaw_openmind_stack.py`
- `tests/test_rebuild_openclaw_openmind_stack.py`

### 3. Added live negative runtime probes to the verifier

Extended `ops/verify_openclaw_openmind_stack.py` to run two explicit negative probes from `main`:

- `sessions_spawn`
- `subagents`

For each probe the verifier now checks:

- the assistant returns the expected `*_UNAVAILABLE` token
- the transcript contains no successful tool call/result for the blocked tool

Added test coverage in:

- `tests/test_verify_openclaw_openmind_stack.py`

### 4. Refreshed review-safe evidence

Updated:

- `docs/reviews/openclaw_openmind_verifier_lean_20260309.md`
- `docs/reviews/openclaw_openmind_verifier_ops_20260309.md`
- `docs/reviews/openclaw_openmind_topology_review_bundle_20260309.md`
- `docs/integrations/openclaw_openmind_best_practice_blueprint_20260309.md`
- `docs/dev_log/2026-03-09_openclaw_openmind_best_practice_rebuild.md`

## Validation

### Narrow regression

```bash
./.venv/bin/pytest -q \
  tests/test_sync_review_repo.py \
  tests/test_rebuild_openclaw_openmind_stack.py \
  tests/test_verify_openclaw_openmind_stack.py

./.venv/bin/python -m py_compile \
  ops/sync_review_repo.py \
  scripts/rebuild_openclaw_openmind_stack.py \
  ops/verify_openclaw_openmind_stack.py \
  tests/test_sync_review_repo.py \
  tests/test_rebuild_openclaw_openmind_stack.py \
  tests/test_verify_openclaw_openmind_stack.py
```

Result: pass.

### Live verification

Ops mode:

```bash
./.venv/bin/python scripts/rebuild_openclaw_openmind_stack.py \
  --state-dir /home/yuanhaizhou/.home-codex-official/.openclaw \
  --topology ops \
  --prune-volatile

systemctl --user daemon-reload
systemctl --user restart openclaw-gateway.service

./.venv/bin/python ops/verify_openclaw_openmind_stack.py \
  --state-dir /home/yuanhaizhou/.home-codex-official/.openclaw \
  --expected-topology ops
```

Result:

- `main_sessions_spawn_negative_probe = PASS`
- `main_subagents_negative_probe = PASS`
- `maintagent_to_main_transcript = PASS`

Lean restore:

```bash
./.venv/bin/python scripts/rebuild_openclaw_openmind_stack.py \
  --state-dir /home/yuanhaizhou/.home-codex-official/.openclaw \
  --topology lean \
  --prune-volatile

systemctl --user daemon-reload
systemctl --user restart openclaw-gateway.service

./.venv/bin/python ops/verify_openclaw_openmind_stack.py \
  --state-dir /home/yuanhaizhou/.home-codex-official/.openclaw \
  --expected-topology lean
```

Result:

- `main_sessions_spawn_negative_probe = PASS`
- `main_subagents_negative_probe = PASS`
- host restored to `lean`

## Outcome

The branch now has public plugin-source reproducibility and direct runtime evidence that `main` cannot use `sessions_spawn` or `subagents` in the supported baseline.
