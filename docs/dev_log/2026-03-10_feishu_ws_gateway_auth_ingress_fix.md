# 2026-03-10 Feishu WS Gateway Auth / Ingress Fix

## Symptom

The Feishu chain returned an error while the API log showed:

- `POST /v2/advisor/advise HTTP/1.1" 401 Unauthorized`

This looked like a Feishu failure, but the webhook handler itself was not the
caller.

## Root Cause

`chatgptrest.advisor.feishu_ws_gateway` was still using an outdated Advisor API
default:

- URL defaulted to `http://127.0.0.1:18711/v2/advisor/advise`
- no `X-Api-Key` header was sent

Current Advisor v3 ingress runs on `18713` and typically requires
`X-Api-Key: $OPENMIND_API_KEY`.

## Fix

1. Default WS-gateway Advisor URL changed to `http://127.0.0.1:18713/v2/advisor/advise`
2. Added `_advisor_api_headers()`:
   - prefer `ADVISOR_API_KEY`
   - fallback to `OPENMIND_API_KEY`
3. WS gateway now uses those headers on every Advisor API call

## Validation

- `./.venv/bin/pytest -q tests/test_feishu_ws_gateway.py tests/test_feishu_async.py`
- `./.venv/bin/python -m py_compile chatgptrest/advisor/feishu_ws_gateway.py tests/test_feishu_ws_gateway.py`

## Note

This fix targets the Feishu **WebSocket gateway** path, not the
`/v2/advisor/webhook` handler. The webhook handler was already auth-exempt at
router level and uses direct in-process advisor execution.
