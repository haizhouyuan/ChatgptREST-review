# 2026-03-26 Low-Level Ask Live Smoke Auth Path Walkthrough v1

## Why this was still needed

`5af3120` fixed the runtime behavior, but one reviewer gap remained: another operator could not reliably reproduce the live `/v1/jobs` outcomes from raw HTTP.

That was not a policy bug. It was an observability/documentation gap.

The request path has three different gates:

1. bearer auth middleware
2. write trace-header guard
3. low-level ask guard

If an operator only knows about step 3, they will see `401 unauthorized` or `400 missing_trace_headers` and conclude the live runtime is inconsistent, even though the low-level ask layer is behaving correctly.

## Why the helper reads the env file directly

The live service tokens are authoritative at service runtime, not in the current shell.

Using a helper that reads `~/.config/chatgptrest/chatgptrest.env` solves two practical problems:

- avoids stale shell state
- avoids assuming that the reviewer knows whether this host expects `CHATGPTREST_API_TOKEN` or `CHATGPTREST_OPS_TOKEN`

The helper still allows explicit `--bearer-token`, but the default path is now “use the same token source the service itself was launched with”.

## Why the smoke matrix is shaped this way

The helper intentionally validates both negative and positive paths:

- negative HMAC path:
  - unsigned `chatgptrest-admin-mcp`
  - unsigned `chatgptrestctl-maint`
- negative intent path:
  - deterministic `planning-wrapper` sufficiency-gate probe
- positive gray-zone classify path:
  - substantive `planning-wrapper` JSON review with inline proposal content

That matrix proves different layers independently:

- auth
- intent sufficiency
- gray-zone allow path

## What this closes

This does not change trust class or auth mode for wrappers.

What it closes is narrower and operationally important:

- reviewers now have a reproducible, scriptable, external-facing path to verify that live `/v1/jobs` really reaches ask guard
- the “service reloaded, but I still only see 401” ambiguity is removed

## What remains afterwards

The remaining security hardening is still the same strategic follow-up:

- evaluate HMAC for `openclaw-wrapper`
- evaluate HMAC for `planning-wrapper`
- evaluate HMAC for `advisor-automation`

That is a trust-model change, not a smoke reproducibility issue.
