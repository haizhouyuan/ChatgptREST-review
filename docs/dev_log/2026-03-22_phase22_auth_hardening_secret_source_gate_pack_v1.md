# Phase 22 Pack: Auth Hardening Secret Source Gate

## Goal

Add a scoped gate that proves the current public surface is not only live, but also operating under a minimally hardened auth and secret-source posture.

## Scope

This phase checks five things:

1. live advisor health reports `auth.mode=strict`
2. secret source exists in local home config, outside the repo
3. public client allowlist is explicit and wildcard-free
4. tracked repo files do not contain literal auth secret values
5. Phase 16 live auth/allowlist/trace gate is still green

## Non-Goals

This phase is not:

- a full identity-hardening review
- a token rotation audit
- a secret manager migration

## Deliverables

- `chatgptrest/eval/auth_hardening_secret_source_gate.py`
- `ops/run_auth_hardening_secret_source_gate.py`
- `tests/test_auth_hardening_secret_source_gate.py`
- artifact directory:
  - `docs/dev_log/artifacts/phase22_auth_hardening_secret_source_gate_20260322/`

## Important Implementation Detail

The gate must treat the local env file as the canonical secret source for leak scanning. Ambient shell variables may contain placeholders or unrelated values and must not create false positives.
