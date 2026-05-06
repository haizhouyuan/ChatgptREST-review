# 2026-04-04 Gemini CDP new_page retry narrowing walkthrough v1

## What I changed

I narrowed Gemini CDP recovery in `_open_gemini_page()` so the extra local retry only applies to `BrowserContext.new_page()` closed-target failures.

I explicitly did **not** keep the earlier broader version that retried the whole `_open_over_cdp()` path on any generic `TargetClosedError`.

## Why I changed it this way

A codex 5.4 xhigh red-team review correctly flagged that the first version was broader than the intent. Because `_open_over_cdp()` still included navigation, retrying the whole path on any `TargetClosedError` would have expanded behavior beyond the intended bootstrap fix.

So I accepted that critique and reworked the batch to:

- retry only the explicit `BrowserContext.new_page/context.new_page` site
- spend that local retry at most once across the whole `_open_gemini_page()` call
- preserve restart/fallback behavior for everything else
- re-check reuse-enabled Gemini tabs after the fresh attach
- add regression tests for both positive and negative boundaries

## What I verified

- focused Gemini unit/regression suites passed
- neighboring CDP reuse / CDP ws fallback / infra retry tests also passed
- live gate was re-attempted, then interrupted fail-closed when it did not self-terminate in the short review window
- direct DB and artifact inspection showed live W1 is still blocked by a newer send-side blank-idempotency/empty-error issue

## Current status after this batch

- This batch is worth keeping.
- It narrows a real risk surface and locks the intended scope with tests.
- But it is **not** the final W1 fix.
- The next investigation should move to the same-runtime blank unsent idempotency replay path surfaced by live job `8276d9afe7864619ac10e27a6171259f`.
