# 2026-03-27 Wrapper Low-Level Governance Live Validation v1

## Goal

Prove that the wrapper-governance lockdown is not only present in repo code, but is also loaded into the live API/MCP processes.

## Runtime

- `chatgptrest-api.service`
  - `ActiveEnterTimestamp=Fri 2026-03-27 13:25:23 CST`
- `chatgptrest-mcp.service`
  - `ActiveEnterTimestamp=Fri 2026-03-27 13:25:23 CST`

New live secret added before reload:

- `CHATGPTREST_ASK_HMAC_SECRET_PLANNING_WRAPPER`

## Smoke

Command:

```bash
./.venv/bin/python ops/run_low_level_ask_live_smoke.py
```

## Result

Smoke result was `ok=true`.

Confirmed live behaviors:

- unsigned `chatgptrest-admin-mcp` => `403 low_level_ask_client_auth_failed`
- unsigned `chatgptrestctl-maint` via ops-token fallback path => `403 low_level_ask_client_auth_failed`
- signed `chatgptrestctl-maint` => `200` + `job_id`
- signed `chatgptrest-admin-mcp` => `200` + `job_id`
- unsigned `planning-wrapper` => `403 low_level_ask_client_auth_failed`
- signed `planning-wrapper` sufficiency probe => `403 low_level_ask_intent_blocked` with `reason=sufficiency_gate`
- signed substantive `planning-wrapper` review => `200` + `job_id`
- immediate duplicate substantive `planning-wrapper` review => `409 low_level_ask_duplicate_recently_submitted`
- `openclaw-wrapper` low-level probe => `403 low_level_ask_surface_not_allowed`
- `advisor_ask` alias low-level probe => `403 low_level_ask_surface_not_allowed`

## Cleanup

The smoke created three real jobs:

- two signed maintenance Gemini jobs
- one substantive planning ChatGPT job

Observed cleanup outcome:

- the two Gemini maintenance jobs had already completed by the time cleanup ran
- the planning substantive job was successfully canceled with `reason=smoke_cleanup`

## Conclusion

The remaining live low-level wrapper surface is now:

- `planning-wrapper`: allowed, but only with HMAC + runtime controls

The explicitly denied external low-level wrapper identities are now:

- `openclaw-wrapper`
- `advisor-automation`
- `finbot-wrapper`

This means wrapper regressions now fail closed at live ingress instead of silently producing unmanaged low-level ask traffic.
