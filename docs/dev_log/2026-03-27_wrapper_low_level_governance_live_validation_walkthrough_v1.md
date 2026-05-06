# 2026-03-27 Wrapper Low-Level Governance Live Validation Walkthrough v1

## Why a separate live record

The governance lockdown itself was already committed in repo code and tests.

This follow-up record exists to prove the live process was actually reloaded and that the runtime contract matches the repo contract.

## What was validated

Three different classes of behavior were verified live:

1. HMAC enforcement

- unsigned maintenance callers are rejected
- signed maintenance callers succeed
- unsigned planning wrapper is rejected

2. Intent/runtime policy

- planning sufficiency probes are still blocked as low-value microtasks
- planning substantive review asks are accepted
- immediate duplicates are rejected using runtime fingerprinting

3. Surface lockdown

- `openclaw-wrapper` cannot use external low-level ask
- `advisor_ask` alias cannot use external low-level ask

## Why this closes the loop

Before this slice, the system could still be misread as:

- "maintenance is hardened, but wrappers are mostly name-based"

After this slice, the live answer is narrower and much safer:

- only one automation wrapper keeps low-level ask
- that wrapper is HMAC-scoped
- it is rate-contained by concurrency and duplicate suppression
- other wrapper-like identities are denied at ingress

## Operational note

The live smoke helper is now the canonical operator replay path for this surface:

- [ops/run_low_level_ask_live_smoke.py](/vol1/1000/projects/ChatgptREST/ops/run_low_level_ask_live_smoke.py)

If this surface regresses later, the first check should be:

1. confirm the services are on the expected reload timestamp
2. run the live smoke helper
3. compare which branch of the matrix changed
