# V1 Bearer Auth Scope Fix

Date: 2026-03-11

## Problem

After enabling `CHATGPTREST_API_TOKEN` and `CHATGPTREST_OPS_TOKEN` for internal go-live hardening, the app-level auth middleware in `chatgptrest/api/app.py` started enforcing bearer auth on every route, including `/v2/*`.

That broke internal callers which were correctly using the existing `/v2` contract:

- route-level `OPENMIND_API_KEY`
- no bearer token requirement

The failure surfaced immediately in `agent_task_closeout.sh` telemetry mirroring, which began returning `401` on `/v2/telemetry/ingest`.

## Fix

- scope the app-level bearer middleware to `/v1/*` only
- leave `/v2/*` on the existing route-level `OPENMIND_API_KEY` contract

## Verification

- `/v1/health` without bearer returns `401`
- `/v1/health` with bearer returns `200`
- `/v1/advisor/recall` with bearer and `source_scope=["planning_review"]` returns `planning_review_pack` hits
- `/v2/policy/hints` with `X-Api-Key` returns `200`
- `agent_task_closeout.sh` telemetry mirroring to `/v2/telemetry/ingest` resumes normal success

## Outcome

- internal go-live hardening stays in place for `/v1`
- `/v2` keeps its documented strict auth behavior
- existing cognitive/telemetry callers do not need to learn a second auth layer
