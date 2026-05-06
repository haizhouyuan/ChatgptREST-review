# 2026-03-09 OpenClaw OpenMind Review Hardening Round 11

## Why

The external topology review still found two evidence-chain problems even after the earlier `sessions_spawn` hardening:

1. the public mirror did not pin the exact source commit under review
2. the review-safe verifier proof still under-described the Feishu hardening surface and lagged behind the live verifier output

This round closes those gaps so the next external review sees a self-consistent public branch:

- `REVIEW_CONTEXT.md` now includes the source commit
- the public mirror now emits `REVIEW_SOURCE.json`
- the live verifier now asserts the full Feishu tool surface is disabled (`doc/chat/wiki/drive/perm/scopes`)
- review-safe lean/ops snapshots were refreshed from the latest live runs

## What Changed

- updated `ops/sync_review_repo.py`
  - propagate `git rev-parse HEAD` into `generate_review_context()`
  - write `REVIEW_SOURCE.json` into the synced public review repo
- updated `ops/verify_openclaw_openmind_stack.py`
  - replace the old single-flag Feishu check with a full `feishu_tools_disabled` assertion
- updated `tests/test_sync_review_repo.py`
  - align the review-safe snapshot expectation to the actual verifier report title
  - verify `REVIEW_SOURCE.json` content
- refreshed review docs
  - `docs/reviews/openclaw_openmind_topology_review_bundle_20260309.md`
  - `docs/reviews/openclaw_openmind_verifier_ops_20260309.md`
  - `docs/reviews/openclaw_openmind_verifier_lean_20260309.md`
  - `docs/integrations/openclaw_openmind_best_practice_blueprint_20260309.md`
  - `docs/dev_log/2026-03-09_openclaw_openmind_best_practice_rebuild.md`

## Validation

Local regression:

```bash
./.venv/bin/pytest -q tests/test_sync_review_repo.py tests/test_verify_openclaw_openmind_stack.py
./.venv/bin/python -m py_compile \
  ops/sync_review_repo.py \
  ops/verify_openclaw_openmind_stack.py \
  tests/test_sync_review_repo.py \
  tests/test_verify_openclaw_openmind_stack.py
```

Live proof:

```bash
./.venv/bin/python scripts/rebuild_openclaw_openmind_stack.py \
  --state-dir /vol1/1000/home-yuanhaizhou/.home-codex-official/.openclaw \
  --openclaw-bin /vol1/1000/home-yuanhaizhou/.home-codex-official/.local/share/openclaw-2026.3.7/node_modules/openclaw/openclaw.mjs \
  --topology ops --prune-volatile
systemctl --user restart openclaw-gateway.service
./.venv/bin/python ops/verify_openclaw_openmind_stack.py \
  --state-dir /vol1/1000/home-yuanhaizhou/.home-codex-official/.openclaw \
  --openclaw-bin /vol1/1000/home-yuanhaizhou/.home-codex-official/.local/share/openclaw-2026.3.7/node_modules/openclaw/openclaw.mjs \
  --expected-topology ops

systemctl --user daemon-reload
./.venv/bin/python scripts/rebuild_openclaw_openmind_stack.py \
  --state-dir /vol1/1000/home-yuanhaizhou/.home-codex-official/.openclaw \
  --openclaw-bin /vol1/1000/home-yuanhaizhou/.home-codex-official/.local/share/openclaw-2026.3.7/node_modules/openclaw/openclaw.mjs \
  --topology lean --prune-volatile
systemctl --user restart openclaw-gateway.service
./.venv/bin/python ops/verify_openclaw_openmind_stack.py \
  --state-dir /vol1/1000/home-yuanhaizhou/.home-codex-official/.openclaw \
  --openclaw-bin /vol1/1000/home-yuanhaizhou/.home-codex-official/.local/share/openclaw-2026.3.7/node_modules/openclaw/openclaw.mjs \
  --expected-topology lean
```

Artifact directories:

- ops proof: `artifacts/verify_openclaw_openmind/20260309T044203Z`
- lean proof: `artifacts/verify_openclaw_openmind/20260309T044416Z`

## Result

Both live verifier runs passed after the hardening changes, and the review-safe documentation now matches the live verifier semantics:

- `security_summary = critical=0 warn=2 info=1`
- residual findings:
  - `summary.attack_surface`
  - `gateway.trusted_proxies_missing`
  - `fs.state_dir.symlink`
- Feishu hardening proof now covers the full tool surface instead of only `doc=false`
