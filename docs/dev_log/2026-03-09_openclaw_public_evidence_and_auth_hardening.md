# 2026-03-09 OpenClaw Public Evidence And Auth Hardening

## Summary

Closed the two public-review blockers from ChatGPT Pro round `95f425c8f2494d38bf70ce1bd7699420`:

1. Public review branch lacked machine-readable runtime evidence.
2. `/v2/advisor/*` was not fail-closed by code default.

## Changes

- Changed `chatgptrest/api/routes_advisor_v3.py` to default `OPENMIND_AUTH_MODE` to `strict`.
- Updated v3 advisor tests to run with explicit auth headers in strict mode and added a fail-closed default regression.
- Updated `ops/nginx_openmind.conf` and the OpenClaw/OpenMind blueprint to document strict advisor auth as the production baseline.
- Removed the repo skill baseline from `maintagent`; it now stays a pure minimal watchdog lane.
- Extended `ops/verify_openclaw_openmind_stack.py` to:
  - verify unauthenticated `/v2/advisor/ask` is rejected
  - publish review-safe evidence under `docs/reviews/` and `docs/reviews/evidence/openclaw_openmind/`
  - mirror raw verifier JSON, redacted config snapshots, transcript excerpts, and advisor auth probe results
- Updated the public review bundle to reference the mirrored evidence instead of local-only `artifacts/`.

## Validation

Targeted tests:

```bash
./.venv/bin/pytest -q tests/test_routes_advisor_v3_security.py tests/test_advisor_v3_end_to_end.py tests/test_openclaw_cognitive_plugins.py
./.venv/bin/pytest -q tests/test_rebuild_openclaw_openmind_stack.py tests/test_verify_openclaw_openmind_stack.py
./.venv/bin/python -m py_compile \
  chatgptrest/api/routes_advisor_v3.py \
  ops/verify_openclaw_openmind_stack.py \
  scripts/rebuild_openclaw_openmind_stack.py \
  tests/test_routes_advisor_v3_security.py \
  tests/test_advisor_v3_end_to_end.py \
  tests/test_rebuild_openclaw_openmind_stack.py \
  tests/test_verify_openclaw_openmind_stack.py
```

Live proofs:

```bash
./.venv/bin/python scripts/rebuild_openclaw_openmind_stack.py --state-dir /home/yuanhaizhou/.home-codex-official/.openclaw --topology lean
systemctl --user daemon-reload
systemctl --user restart openclaw-gateway.service
./.venv/bin/python ops/verify_openclaw_openmind_stack.py \
  --state-dir /home/yuanhaizhou/.home-codex-official/.openclaw \
  --expected-topology lean \
  --publish-review-evidence \
  --review-label 20260309

./.venv/bin/python scripts/rebuild_openclaw_openmind_stack.py --state-dir /home/yuanhaizhou/.home-codex-official/.openclaw --topology ops
systemctl --user daemon-reload
systemctl --user restart openclaw-gateway.service
./.venv/bin/python ops/verify_openclaw_openmind_stack.py \
  --state-dir /home/yuanhaizhou/.home-codex-official/.openclaw \
  --expected-topology ops \
  --publish-review-evidence \
  --review-label 20260309
```

Key published evidence:

- `docs/reviews/openclaw_openmind_verifier_lean_20260309.json`
- `docs/reviews/openclaw_openmind_verifier_ops_20260309.json`
- `docs/reviews/evidence/openclaw_openmind/B1/openclaw_openmind_config_lean_20260309.json`
- `docs/reviews/evidence/openclaw_openmind/B1/openclaw_openmind_config_ops_20260309.json`
- `docs/reviews/evidence/openclaw_openmind/B1/openclaw_openmind_transcript_lean_20260309.json`
- `docs/reviews/evidence/openclaw_openmind/B1/openclaw_openmind_transcript_ops_20260309.json`
- `docs/reviews/evidence/openclaw_openmind/B2/openmind_advisor_auth_lean_20260309.json`
- `docs/reviews/evidence/openclaw_openmind/B2/openmind_advisor_auth_ops_20260309.json`

## Notes

- The live host was left in `ops` during evidence generation and should be returned to `lean` after final sync/review.
- Public review must consume mirrored `docs/reviews/evidence/...` files; `artifacts/` stays excluded from `ops/sync_review_repo.py`.
