# Phase 21 Pack: API Provider Delivery Gate

## Goal

Add a live gate that proves a covered advisor request can:

- enter the live advisor host,
- reach a completed delivery state,
- persist a completed trace snapshot,
- and emit a same-trace `llm_connector llm.call_completed` event.

## Why This Phase Exists

Earlier gates had already proved:

- public surface readiness,
- covered delivery-chain readiness,
- and dynamic OpenClaw replay.

The missing proof was narrower and more specific:

- a real API-provider call, on a real live route, correlated to the same business `trace_id`.

## Scope

This phase is intentionally scoped to:

- `POST /v2/advisor/advise`
- current live advisor host on `http://127.0.0.1:18711`
- covered quick-answer API-provider path only

This phase is explicitly **not**:

- a generic external-provider proof
- a web-provider proof
- an MCP-provider proof
- a full-stack deployment proof

## Deliverables

- `chatgptrest/eval/api_provider_delivery_gate.py`
- `ops/run_api_provider_delivery_gate.py`
- `tests/test_api_provider_delivery_gate.py`
- artifact directory:
  - `docs/dev_log/artifacts/phase21_api_provider_delivery_gate_20260322/`

## Acceptance

Gate must fail unless all of the following are true for one live trace:

1. advise response is `200`
2. advise response status is `completed`
3. selected route is `hybrid`
4. route result route is `quick_ask`
5. controller status is `DELIVERED`
6. persisted trace snapshot is `completed`
7. EventBus contains same-trace `llm_connector / llm.call_completed`
8. correlated event exposes non-empty provider model metadata
