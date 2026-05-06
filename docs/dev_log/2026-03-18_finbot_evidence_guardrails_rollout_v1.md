# Finbot Evidence Guardrails Rollout v1

Date: 2026-03-18

## Scope

Implemented the first repo-grounded dual-advisor tranche for `finbot` / `finbotfree`:

- claim-level evidence bindings with exact-excerpt preference
- claim-level counterevidence packets
- deterministic posture guard for free-tier / missing-evidence cases
- promotion packet persistence and dashboard exposure

## Code Changes

### Core pipeline

- `chatgptrest/finbot.py`
  - extended `opportunity_deepen()` to write:
    - `claim_evidence_bindings.json`
    - `counterevidence_packets.json`
    - `policy_result.json`
    - `promotion_packet.json`
  - persisted the new artifacts into `research_package.json`
  - added policy-driven posture capping and promotion metadata
  - exposed promotion packets through `theme_batch_run()` and `daily_work()`
  - fixed markdown assembly so claim ledger / critical unknowns are not rendered inside the core-claims loop

### New pure modules

- `chatgptrest/finbot_modules/evidence_binding.py`
- `chatgptrest/finbot_modules/negative_evidence.py`
- `chatgptrest/finbot_modules/posture_guard.py`
- `chatgptrest/finbot_modules/promotion_packet.py`

### Dashboard

- `chatgptrest/dashboard/templates/investor_opportunity_detail.html`
  - added policy guard and promotion packet cards
  - added evidence audit and counterevidence packet panels
  - stopped the claim lane from silently inventing a fallback source when primary evidence is missing
  - rendered missing-primary warnings before generic source references

## Guardrail Semantics

- `missing_primary_evidence` now means the load-bearing claim still lacks an exact primary excerpt.
- `missing_counterevidence` now requires material skeptic evidence.
  Placeholder packets with `stance=no_refute_found` do not satisfy the guard.
- `promotion_packet.blocked_by` is synchronized with final `blocking_facts` before artifacts are written.

## Verification

### Static / test

Run:

```bash
TMPDIR=/vol1/1000/projects/ChatgptREST/.codex_tmp/pytest-tmp \
  ./.venv/bin/python -m py_compile \
  chatgptrest/finbot.py \
  chatgptrest/finbot_modules/evidence_binding.py \
  chatgptrest/finbot_modules/negative_evidence.py \
  chatgptrest/finbot_modules/posture_guard.py \
  chatgptrest/finbot_modules/promotion_packet.py \
  tests/test_finbot.py \
  tests/test_finbot_dashboard_service_integration.py

TMPDIR=/vol1/1000/projects/ChatgptREST/.codex_tmp/pytest-tmp \
  ./.venv/bin/pytest -q \
  tests/test_finbot.py \
  tests/test_finbot_dashboard_service_integration.py
```

Result:

- `34 passed`

### Runtime expectation

- `chatgptrest-finbotfree-daily-work.timer` remains enabled and runs every 4 hours.
- `chatgptrest-finbotfree-theme-batch.timer` remains enabled and runs nightly.
- Both services read credentials from `/vol1/maint/MAIN/secrets/credentials.env` and use:
  - `FINBOT_TIER=free`
  - `OPENROUTER_DEFAULT_MODEL=nvidia/nemotron-3-super-120b-a12b:free`

## Notes

- Existing unrelated dirty changes under `ops/systemd/chatgptrest-finbot-*.service` were not modified or reverted as part of this rollout.
