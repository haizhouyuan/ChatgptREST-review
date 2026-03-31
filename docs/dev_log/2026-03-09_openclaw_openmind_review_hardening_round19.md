# 2026-03-09 OpenClaw OpenMind Review Hardening Round 19

## Trigger

The latest external review rounds moved from topology disagreements to two narrower proof-quality blockers:

- controlled access was not *explicitly proven* from the public review package
  - `auth.mode=token` was visible, but token presence was not separately asserted
  - `allowTailscale` was still inheriting ambient host state in the generated config
- the public provenance chain was not self-contained
  - `REVIEW_SOURCE.json` still pointed back to a local filesystem repo path
- the lean baseline still looked broader than intended
  - `main` inherited session messaging/history tools that were not part of the supported single-agent baseline

While closing those proof gaps in the rebuild + verifier path, the live `ops` run also exposed a real runtime regression:

- OpenMind plugins were starting without an API key after the gateway config became deterministic, causing `401 Invalid or missing API key`

## Changes

- updated `scripts/rebuild_openclaw_openmind_stack.py`
  - `lean` now explicitly denies `sessions_send`, `sessions_list`, and `sessions_history` in addition to `sessions_spawn`, `subagents`, automation, UI, and image
  - generated gateway config now pins:
    - `auth.mode = token`
    - `auth.token` present
    - `auth.allowTailscale = false`
    - `tailscale.mode = off`
    - `tailscale.resetOnExit = false`
    - `controlUi.allowInsecureAuth = false`
  - generated plugins config now reads `OPENMIND_API_KEY` from the shared env file and injects it into OpenMind plugin endpoints
- updated `ops/verify_openclaw_openmind_stack.py`
  - added explicit review-facing checks for:
    - `gateway_auth_token_present`
    - `gateway_tailscale_disabled`
- updated `ops/sync_review_repo.py`
  - `REVIEW_SOURCE.json` now records the public GitHub source repo URL and commit URL instead of a local filesystem path
- updated review-facing docs
  - `docs/integrations/openclaw_openmind_best_practice_blueprint_20260309.md`
  - `docs/dev_log/2026-03-09_openclaw_openmind_best_practice_rebuild.md`
  - `docs/reviews/openclaw_openmind_topology_review_bundle_20260309.md`
  - refreshed review-safe verifier snapshots for both `ops` and `lean`

## Validation

Targeted tests:

```bash
./.venv/bin/pytest -q \
  tests/test_rebuild_openclaw_openmind_stack.py \
  tests/test_verify_openclaw_openmind_stack.py \
  tests/test_sync_review_repo.py

./.venv/bin/python -m py_compile \
  scripts/rebuild_openclaw_openmind_stack.py \
  ops/verify_openclaw_openmind_stack.py \
  ops/sync_review_repo.py \
  tests/test_rebuild_openclaw_openmind_stack.py \
  tests/test_verify_openclaw_openmind_stack.py \
  tests/test_sync_review_repo.py
```

Live rebuild + verification:

```bash
./.venv/bin/python scripts/rebuild_openclaw_openmind_stack.py --topology ops
systemctl --user daemon-reload
systemctl --user restart openclaw-gateway.service
./.venv/bin/python ops/verify_openclaw_openmind_stack.py \
  --state-dir /home/yuanhaizhou/.home-codex-official/.openclaw \
  --expected-topology ops

./.venv/bin/python scripts/rebuild_openclaw_openmind_stack.py --topology lean
systemctl --user daemon-reload
systemctl --user restart openclaw-gateway.service
./.venv/bin/python ops/verify_openclaw_openmind_stack.py \
  --state-dir /home/yuanhaizhou/.home-codex-official/.openclaw \
  --expected-topology lean
```

## Outcome

The latest live verifier outputs now prove the review-facing claims directly from the generated baseline:

- `ops`: `artifacts/verify_openclaw_openmind/20260309T095818Z/verify_openclaw_openmind_stack.md`
- `lean`: `artifacts/verify_openclaw_openmind/20260309T095721Z/verify_openclaw_openmind_stack.md`

Both runs pass the new controlled-access checks:

- `gateway_auth_token_mode`
- `gateway_auth_token_present`
- `gateway_tailscale_disabled`

The live gateway also confirms the runtime fix landed:

- `openmind-advisor: ready`
- `openmind-graph: ready`
- `openmind-memory: ready`
- `openmind-telemetry: ready`

This round closes the remaining known review-package blockers that were still attributable to our own public evidence:

- no more local-path provenance in `REVIEW_SOURCE.json`
- no ambient `allowTailscale=true` leakage
- no ambiguous token-proof gap
- no extra session messaging surface in the `lean` baseline
