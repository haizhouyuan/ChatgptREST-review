# OpenClaw Guardian Auth And Agent Resolution

Date: 2026-03-11

## Problem

After enabling bearer auth on ChatgptREST `/v1` surfaces, `ops/openclaw_guardian_run.py` started failing its patrol HTTP probes because it did not send bearer auth for:

- `/healthz`
- `/v1/ops/status`
- `/v1/issues`

At the same time, the guardian runtime still assumed a dedicated OpenClaw agent id existed (`maintagent`, then `chatgptrest-guardian`), but the current live OpenClaw state only exposes a single `main` agent under:

- `/home/yuanhaizhou/.home-codex-official/.openclaw/agents/main`

## Fix

- guardian HTTP helpers now attach bearer auth automatically for `/healthz`, `/health`, `/v1/*`, and `/v1/ops/*`
- the guardian runtime now resolves its target agent dynamically:
  - use the requested guardian agent if it exists in `OPENCLAW_STATE_DIR`
  - otherwise fall back to `main` when the live OpenClaw state is single-agent
- the manual wake script now mirrors the same fallback behavior

## Verification

- `tests/test_openclaw_guardian_issue_sweep.py`
- direct guardian probe with service-like env now reports:
  - `health.ok = true`
  - `ops_status.ok = true`
- guardian no longer fails solely because `/v1` auth was enabled

## Remaining Reality

- the current live OpenClaw gateway still has an upstream model-side problem on the main lane:
  - `openai-codex` refresh token reuse (`401 refresh_token_reused`)
  - fallback `google-gemini-cli` timeout in the live verifier path
- that is separate from the guardian auth fix and still affects interactive OpenClaw usage
