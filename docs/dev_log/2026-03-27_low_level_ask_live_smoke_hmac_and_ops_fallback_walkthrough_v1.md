# 2026-03-27 Low-Level Ask Live Smoke HMAC And OPS Fallback Walkthrough v1

## Why this slice mattered

The previous live smoke helper was already enough to prove that:

- ask guard was reachable
- unsigned maintenance requests did not silently bypass HMAC
- gray-zone wrapper behavior matched the intended policy

But there were still two blind spots for reviewers:

1. a negative HMAC result is not the same as proving the positive HMAC path
2. documenting OPS-token fallback is not the same as proving the live bearer middleware accepts it on `/v1/jobs*`

This slice closes both by making the smoke helper exercise those paths directly.

## Design choice

The helper now uses the same building block as the real clients:

- `build_registered_client_hmac_headers(...)`

That matters because it keeps the smoke path anchored to the actual runtime contract instead of hand-rolling a second implementation.

The bearer path is also made explicit:

- if only one token exists, the helper uses what is available
- if both API and OPS tokens exist and differ, the helper exercises both so the OPS fallback is really observed, not inferred

## Why signed maintenance probes stop at job creation

For this slice, success means:

- global bearer middleware accepted the request
- trace header gate accepted the request
- registered client resolution matched the correct maintenance profile
- HMAC validation succeeded
- low-level ask authorization accepted the request

That is already fully proven when `/v1/jobs` returns `200` with a `job_id`.

Waiting for the downstream provider would test a different layer and would make the smoke noisier without increasing confidence in the ingress contract itself.

## What the helper now proves in one run

- unsigned maintenance probe is rejected
- signed maintenance probe is accepted
- OPS token fallback works on `/v1/jobs*` when it is actually configured on the host
- deterministic sufficiency-gate block still holds
- substantive wrapper review still gets through

That gives operators one scriptable matrix instead of five manual cURL experiments.

## What remains after this

The remaining open work is not smoke evidence anymore. It is trust-model hardening:

- `openclaw-wrapper`
- `planning-wrapper`
- `advisor-automation`

Those identities are still governed by registry + authorization + guard, not by HMAC.
