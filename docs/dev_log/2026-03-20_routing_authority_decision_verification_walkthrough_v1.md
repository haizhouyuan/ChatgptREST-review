# 2026-03-20 Routing Authority Decision Verification Walkthrough v1

## What I checked

This verification re-audited:

- [2026-03-20_routing_authority_decision_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_routing_authority_decision_v1.md)

I focused on four questions:

1. Is `RoutingFabric` really live in the current advisor runtime?
2. Is `LLMConnector._select_model()` really the concrete API execution layer?
3. Are `ModelRouter` and `routing_engine` actually dormant in the live runtime?
4. Is ingress lane authority really as simple as `/v2/advisor/ask + _ROUTE_TO_EXECUTION + ControllerEngine.ask(...)`?

## What held up

These parts of the document survived verification:

- `RoutingFabric` is live and attached to the connector
- graph/report do prefer `RoutingFabric` with API fallback
- `RoutingFabric` does not directly execute concrete API providers
- `LLMConnector._select_model()` is the current API model-chain chooser
- `ModelRouter` is not wired into the live advisor runtime
- `routing_engine` is not in the live advisor runtime composition root

That means the document's middle and lower routing layers are materially sound.

## What did not hold up cleanly

The remaining problems are concentrated in layer A, the ingress lane side.

### 1. `/v3/agent/turn` was left out

Current public live asks are explicitly supposed to go through `/v3/agent/turn`, and that endpoint performs real dispatch work:

- image goal
- consultation fan-out
- Gemini research special-case
- only then fallback into `ControllerEngine.ask(...)`

So the ingress layer cannot be modeled only from `/v2/advisor/ask`.

### 2. The lane mapping is duplicated

There is still no single route-mapping source:

- `/v2/advisor/ask` uses `_ROUTE_TO_EXECUTION`
- `/v3/agent/turn` carries an inline duplicate mapping

That is still unresolved authority duplication.

### 3. `ControllerEngine.ask(...)` is not the whole story

Inside the controller path, there are at least three live sub-decisions:

- `_plan_async_route()` chooses route and executor hints
- `_resolve_execution_kind()` chooses `job/team/effect`
- `route_mapping` converts route into `provider/preset/kind`

So the document's layer-A phrasing is still too compressed.

### 4. `cc runtime` was over-included

`cc_native` clearly reports outcome back into `RoutingFabric`, but I did not find code showing it actively consumes `RoutingFabric` for provider selection.

So the verified statement is narrower than the document currently claims.

## Why this matters

This is not a cosmetic wording issue.

The next proposed downstream doc is `front_door_contract_v1`. If that doc is written on top of the current routing decision without these corrections, it will inherit the wrong simplification:

- it will treat `/v2/advisor/ask` as the main lane-routing surface
- it may miss the fact that `/v3/agent/turn` already contains live routing decisions
- it may miss the duplicated route-mapping source

## Deliverables

This verification added:

- [2026-03-20_routing_authority_decision_verification_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_routing_authority_decision_verification_v1.md)
- [2026-03-20_routing_authority_decision_verification_walkthrough_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_routing_authority_decision_verification_walkthrough_v1.md)

## Test Note

This was a documentation and code-evidence verification task. No code was changed, and no test suite was run.
