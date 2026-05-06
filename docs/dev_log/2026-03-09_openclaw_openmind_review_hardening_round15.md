# 2026-03-09 OpenClaw OpenMind Review Hardening Round 15

## Trigger

ChatGPT Pro round `18215838302341188bf698d310704ca1` returned `FAIL` with three concrete public-review blockers:

1. the public package did not prove a closed skill surface
2. the public package did not prove a closed plugin surface
3. the public package did not prove the intended gateway hardening posture

## Changes

- tightened `scripts/rebuild_openclaw_openmind_stack.py` so the rebuilt baseline is public-review-safe by construction:
  - `skills.load.extraDirs` is now repo-only: `ChatgptREST/skills-src`
  - `skills.allowBundled` is cleared
  - `main.skills` is now `["chatgptrest-call"]`
  - `maintagent.skills` is now `["chatgptrest-call"]`
  - host-local `LOCAL_PLUGIN_PROVENANCE_PATHS` was removed
  - `env-http-proxy` was removed from the enabled plugin baseline
  - `gateway` is rebuilt into a pinned loopback/token/trusted-proxies posture instead of inheriting the previous gateway block wholesale
- extended `ops/verify_openclaw_openmind_stack.py` so the review-safe verifier now records and checks:
  - repo-only `skills.load.extraDirs`
  - empty `skills.allowBundled`
  - public agent skill sets
  - empty plugin load paths
  - absence of `env-http-proxy`
  - loopback gateway bind
  - configured `trustedProxies`
  - token auth mode
- refreshed review-safe verifier snapshots:
  - `docs/reviews/openclaw_openmind_verifier_ops_20260309.md`
  - `docs/reviews/openclaw_openmind_verifier_lean_20260309.md`
- updated the review bundle so it no longer claims `env-http-proxy` is enabled and no longer treats `gateway.trusted_proxies_missing` as an accepted residual warning

## Validation

Targeted regression:

```bash
./.venv/bin/pytest -q tests/test_rebuild_openclaw_openmind_stack.py tests/test_verify_openclaw_openmind_stack.py tests/test_sync_review_repo.py
./.venv/bin/python -m py_compile scripts/rebuild_openclaw_openmind_stack.py ops/verify_openclaw_openmind_stack.py ops/sync_review_repo.py tests/test_rebuild_openclaw_openmind_stack.py tests/test_verify_openclaw_openmind_stack.py tests/test_sync_review_repo.py
```

Live rebuild + verify:

```bash
./.venv/bin/python scripts/rebuild_openclaw_openmind_stack.py --topology ops
systemctl --user daemon-reload
systemctl --user restart openclaw-gateway.service
./.venv/bin/python ops/verify_openclaw_openmind_stack.py --state-dir /home/yuanhaizhou/.home-codex-official/.openclaw --expected-topology ops

./.venv/bin/python scripts/rebuild_openclaw_openmind_stack.py --topology lean
systemctl --user daemon-reload
systemctl --user restart openclaw-gateway.service
./.venv/bin/python ops/verify_openclaw_openmind_stack.py --state-dir /home/yuanhaizhou/.home-codex-official/.openclaw --expected-topology lean
```

## Outcome

- `ops` and `lean` both passed live verification
- `security_findings` no longer contains `gateway.trusted_proxies_missing`
- the review-safe verifier now shows:
  - repo-only skill directory
  - `chatgptrest-call` as the only public agent skill
  - no host-local plugin load paths
  - no `env-http-proxy`
  - explicit gateway `trustedProxies`
- final host state was returned to `lean`
