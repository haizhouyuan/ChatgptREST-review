# EvoMap Internal Go-Live Activation

Date: 2026-03-11

## Scope

- keep default retrieval unchanged
- enable planning reviewed runtime pack only through explicit opt-in
- pin runtime pack consumption to the approved release bundle
- require bearer auth on `/v1` endpoints for local operator and MCP clients

## Activated Settings

- `CHATGPTREST_PLANNING_RUNTIME_PACK_BUNDLE_DIR` points to:
  - `/vol1/1000/projects/ChatgptREST/artifacts/monitor/planning_runtime_pack_release_bundle/20260311T110948Z`
- `CHATGPTREST_API_TOKEN` configured in the user service env
- `CHATGPTREST_OPS_TOKEN` configured in the user service env
- app-level bearer middleware is active only for `/v1/*`

## Verification

1. Restart `chatgptrest-api.service` so the new env is loaded.
2. Confirm `/v1` rejects unauthenticated requests with `401`.
3. Confirm `/v1` accepts authenticated requests with the configured bearer token.
4. Confirm `/v1/advisor/recall` with `source_scope=["planning_review"]` returns `planning_review_pack` hits.
5. Confirm `/v2` remains in `strict` auth mode and still accepts requests with `X-Api-Key`.

## Rollback

- unset `CHATGPTREST_PLANNING_RUNTIME_PACK_BUNDLE_DIR` to disable the pinned planning pack
- or point it to a previous approved bundle
- use the bundle runbook:
  - `/vol1/1000/projects/ChatgptREST/artifacts/monitor/planning_runtime_pack_release_bundle/20260311T110948Z/rollback_runbook.md`
- unset `CHATGPTREST_API_TOKEN` and `CHATGPTREST_OPS_TOKEN` only if you intentionally want loopback `/v1` back in unauthenticated mode

## Notes

- This activation is for internal go-live only.
- `planning_review_pack` stays explicit opt-in via `planning_mode=true` or `source_scope=["planning_review"]`.
- `execution` stays in review plane; no active knowledge promotion is enabled here.
- `/v2` keeps its route-level `OPENMIND_API_KEY` contract; enabling `/v1` bearer auth does not add a second auth layer to `/v2`.
