# 2026-03-23 Public Agent Effects And Delivery Validation Pack v1

## Goal

Prove that the public-agent northbound surface now projects a stable lifecycle, delivery, and effect model across:

- raw `/v3/agent/turn`
- public MCP `advisor_agent_turn`
- the repo wrapper `chatgptrest_call.py`
- same-session deferred continuation
- cancel
- workspace clarify/effect paths

This validation pack is intentionally scoped to public-surface behavior. It does not claim external provider completion proof or heavy execution approval.

## Validation Components

- Code:
  - [public_agent_effects_delivery_validation.py](/vol1/1000/projects/ChatgptREST/chatgptrest/eval/public_agent_effects_delivery_validation.py)
  - [run_public_agent_effects_delivery_validation.py](/vol1/1000/projects/ChatgptREST/ops/run_public_agent_effects_delivery_validation.py)
  - [test_public_agent_effects_delivery_validation.py](/vol1/1000/projects/ChatgptREST/tests/test_public_agent_effects_delivery_validation.py)
- Live artifact:
  - [report_v1.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/public_agent_effects_delivery_validation_20260323/report_v1.json)
  - [report_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/public_agent_effects_delivery_validation_20260323/report_v1.md)

## Covered Checks

1. API service is running on the refreshed runtime
2. MCP service is running on the refreshed runtime
3. raw API clarify response projects lifecycle + delivery
4. public MCP clarify response projects lifecycle + delivery
5. wrapper stdout + `--out-summary` both project lifecycle/delivery/effects
6. same-session `contract_patch` deferred accept surface projects `accepted`
7. patched session projects `progress`
8. cancel projects `cancelled`
9. workspace clarify projects `effects.workspace_action`

## Acceptance

The package is considered green only if all 9 checks pass in the live runner.
