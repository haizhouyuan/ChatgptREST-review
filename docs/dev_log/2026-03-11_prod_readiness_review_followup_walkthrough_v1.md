# 2026-03-11 Production Readiness Review Follow-up Walkthrough v1

## Scope

This walkthrough records the follow-up patch set applied after the review in:

- `docs/reviews/2026-03-11_prod_readiness_pr122_pr11_review_v1.md`

The goal of this batch was not to reopen the full production-readiness program. It was to update the two active PR branches so the confirmed review findings were either:

- fixed in code
- documented as intentional behavior
- or marked as outdated when the reviewer assumption no longer matched the branch state

Affected branches:

- ChatgptREST: `codex/prod-readiness-fixes-20260311` (`PR #122`)
- OpenClaw: `codex/prod-readiness-fixes-20260311` (`PR #11`)

## Review Follow-up Outcomes

Confirmed review items that were fixed in this batch:

- `H1`: `/v2/advisor/cc-*` control-plane restriction is now attached only to `cc-*` routes, and loopback fallback now uses the raw peer address instead of proxy-derived client IP.
- `H2`: `/v2/advisor/ask` auto-idempotency now ignores volatile tracing/session fields while preserving stable business context.
- `H3`: broader trusted-proxy CIDRs in OpenClaw now emit an explicit warning instead of failing silently.
- `H4`: `openmind-advisor` no longer collapses multiple agents to a single fallback `userId`.
- `M1`: `/health`, `/healthz`, and `/readyz` are now exempt from global Bearer auth when v1 auth tokens are enabled.
- `M2`: guardian now emits a one-time warning when neither ChatgptREST API token nor ops token is configured.
- `M3`: plugin docs now state that OpenClaw sends explicit idempotency keys and should not rely on server-side auto-idempotency when context is volatile.
- `M4`: ChatgptREST now supports canonical `OPENCLAW_*` env names while keeping the historical `OPENCLOW_*` aliases for compatibility.
- `L1`: `openmind-advisor` now uses `SHA-256` to align with server-side hashing.
- `L2`: guardian URL construction now goes through a shared helper instead of repeated string concatenation.

Review items that were not treated as active defects:

- `M5`: outdated on the reviewed PR branch. The OpenClaw branch already propagates `sessionId` and `agentAccountId` through the plugin context path.
- `L3`: not treated as a defect. The compat test imports `validateConfigObject` from a public export path, not an inaccessible private symbol.

## ChatgptREST Branch Update

Committed follow-up patch:

- `97ccc5c` `Harden advisor control/auth and idempotency follow-ups`

Key changes:

- Moved `_require_cc_control_access` off the whole `/v2/advisor` router and onto the `cc-*` endpoints only.
- Switched loopback fallback in `_require_cc_control_access` to `request.client.host` so proxy headers cannot satisfy the implicit local-control path.
- Added stable-context normalization for `/v2/advisor/ask` idempotency and reused the same normalized context for:
  - auto-generated idempotency keys
  - request fingerprints
  - prompt enrichment blocks
  - `input_obj.context_fingerprint`
- Exempted `/health`, `/healthz`, and `/readyz` from global Bearer auth.
- Added canonical `CHATGPTREST_OPENCLAW_*` env names while preserving legacy `CHATGPTREST_OPENCLOW_*` aliases.
- Added guardian warning for missing ChatgptREST auth tokens and consolidated internal API URL joining.
- Updated `openmind-advisor` to:
  - hash with `SHA-256`
  - derive a more stable per-agent `userId`
  - document the explicit idempotency-key contract

## OpenClaw Branch Update

Committed follow-up patch:

- `05975005a` `Warn once on ignored trusted proxy CIDRs`

Key changes:

- Added a one-time warning for unsupported broad CIDRs in trusted-proxy config.
- Kept the existing security posture unchanged: only exact hosts and single-host CIDRs remain trusted.
- Added regression coverage to ensure the warning fires once for a broad CIDR and does not spam repeated calls.

## Validation

ChatgptREST targeted pytest batch passed:

- `tests/test_routes_advisor_v3_security.py`
- `tests/test_advisor_v3_end_to_end.py`
- `tests/test_ops_endpoints.py`
- `tests/test_openclaw_adapter.py`
- `tests/test_openclaw_guardian_issue_sweep.py`
- `tests/test_openclaw_cognitive_plugins.py`

OpenClaw targeted vitest batch passed:

- `src/gateway/net.test.ts`

Scope verification notes:

- `gitnexus_detect_changes()` was run, but GitNexus currently resolves repository-root dirty state and does not isolate the dedicated worktree cleanly.
- For the actual PR delta, final scope verification used the worktree-local `git status` and `git diff --stat` outputs before each commit.

## Residuals

This batch updates the PRs, but it does not replace the earlier production decision:

- the live verifier still needs a fresh rerun on the patched branches
- plaintext runtime secrets still need to be moved out of the active `openclaw.json`
