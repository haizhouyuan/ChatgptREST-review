## Summary

Feishu WS ingress was failing at runtime with:

- `Advisor API 401: {"detail":"Invalid or missing API key"}`

The failure was not in the webhook route or the WS gateway HTTP client code. The
runtime mismatch was in systemd wiring:

- `chatgptrest-api.service` loaded `~/.config/chatgptrest/chatgptrest.env`
- `chatgptrest-feishu-ws.service` loaded only `credentials.env`

That meant the API process had `OPENMIND_API_KEY`, but the Feishu WS process did
not, so `_advisor_api_headers()` built no `X-Api-Key`.

During validation we also confirmed a second runtime mismatch on this host:

- `127.0.0.1:18713` is currently served by a Node/Express process
- the active Python ChatgptREST API on `127.0.0.1:18711` handles `/v2/advisor/advise`

So the Feishu WS gateway needed both:

- shared auth env
- explicit integrated-host `ADVISOR_API_URL`

## Fix

Added a managed unit source:

- `ops/systemd/chatgptrest-feishu-ws.service`

The repo-managed unit now loads both:

- `EnvironmentFile=-%h/.config/chatgptrest/chatgptrest.env`
- `EnvironmentFile=-/vol1/maint/MAIN/secrets/credentials.env`

and pins:

- `Environment=ADVISOR_API_URL=http://127.0.0.1:18711/v2/advisor/advise`

This keeps Feishu app credentials and shared OpenMind advisor auth on the same
runtime contract as the API and other services.

## Validation

- `pytest -q tests/test_feishu_systemd_unit.py tests/test_feishu_ws_gateway.py`
- `python -m py_compile tests/test_feishu_systemd_unit.py`
- `ops/systemd/install_user_units.sh`
- `systemctl --user daemon-reload`
- `systemctl --user restart chatgptrest-feishu-ws.service`
- verified the running Feishu WS process now exposes `OPENMIND_API_KEY`
- verified the managed unit now targets the integrated-host Advisor ingress on `18711`
