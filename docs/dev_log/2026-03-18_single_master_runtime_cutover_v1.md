## Summary

This cutover removes the split runtime arrangement and makes the live ChatgptREST services run from the main checkout:

- repo root: `/vol1/1000/projects/ChatgptREST`
- branch: `master`

The goal was to stop running API/MCP/worker services from separate worktrees and simplify operations to one authoritative master checkout.

## What Changed

The user systemd drop-ins for the runtime services were updated to point to the main checkout:

- `chatgptrest-api.service`
- `chatgptrest-mcp.service`
- `chatgptrest-worker-send.service`
- `chatgptrest-worker-wait.service`

Each service now uses:

- `WorkingDirectory=/vol1/1000/projects/ChatgptREST`
- `PYTHONPATH=/vol1/1000/projects/ChatgptREST`
- `CHATGPTREST_DB_PATH=/vol1/1000/projects/ChatgptREST/state/jobdb.sqlite3`
- `CHATGPTREST_ARTIFACTS_DIR=/vol1/1000/projects/ChatgptREST/artifacts`

The MCP service entrypoint was also aligned to:

- `/vol1/1000/projects/ChatgptREST/chatgptrest_mcp_server.py`

## Main Checkout Hygiene

The main checkout had local strategist/deep-research working state that would have made a direct runtime cutover unsafe.

That state was preserved separately on:

- branch: `tmp/main-checkout-preserve-20260318`
- preserve commit: `ac1f16b chore: preserve local strategist and deep research working state`

After preservation, the main checkout was returned to a clean `master` state before runtime cutover.

## Verification

All four live services are now running from the main checkout:

- `chatgptrest-api.service`
- `chatgptrest-mcp.service`
- `chatgptrest-worker-send.service`
- `chatgptrest-worker-wait.service`

Runtime verification confirmed for each service:

- cwd resolves to `/vol1/1000/projects/ChatgptREST`
- `PYTHONPATH` points to `/vol1/1000/projects/ChatgptREST`
- DB/artifacts paths point to the main checkout `state/` and `artifacts/`

Smoke-risk containment was also re-checked against the new runtime. A guarded probe to `/v1/jobs` with:

- `kind=chatgpt_web.ask`
- `question=hello`
- `params.purpose=smoke`
- `params.preset=auto`

returned:

- `400 live_chatgpt_smoke_blocked`

This confirms the earlier live smoke containment fix remained active after the single-master cutover.

## Outcome

The live runtime no longer depends on:

- `/vol1/1000/worktrees/chatgptrest-dashboard-p0-20260317-clean`
- `/vol1/1000/worktrees/chatgptrest-advisor-agent-facade-20260317`

Those worktrees may still exist for historical inspection, but they are no longer the live runtime source of truth.
