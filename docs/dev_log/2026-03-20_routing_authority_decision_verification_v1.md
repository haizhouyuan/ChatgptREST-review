# 2026-03-20 Routing Authority Decision Verification v1

## Scope

Target under verification:

- [2026-03-20_routing_authority_decision_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_routing_authority_decision_v1.md)

Verification method on `2026-03-20`:

- inspect commit `ee218fd`
- re-check the target document against current code
- verify runtime composition in `advisor/runtime.py`
- verify ingress behavior in `/v2/advisor/ask` and `/v3/agent/turn`
- verify whether `RoutingFabric`, `LLMConnector`, `ModelRouter`, and `routing_engine` are actually wired into live paths

## Verdict

`routing_authority_decision_v1` is substantially better than the earlier authority-matrix treatment of routing, but it is still not safe to freeze as the final routing authority contract.

The document gets three important things right:

1. `RoutingFabric` is not the concrete API execution source of truth.
2. `LLMConnector._select_model()` is the current concrete API model-chain selector.
3. `ModelRouter` and `routing_engine` are not live routing authorities in the current advisor runtime.

But the ingress layer is still modeled too narrowly. The document treats lane routing as if it were centered on `/v2/advisor/ask` plus `_ROUTE_TO_EXECUTION`, while current live ingress behavior is split across:

- `/v2/advisor/ask`
- `ControllerEngine._plan_async_route()` and `_resolve_execution_kind()`
- `/v3/agent/turn` goal-hint dispatch and its own inline `route_mapping`

So this document should be treated as `partially verified`, not as the final freeze artifact.

## Confirmed

The following claims in [2026-03-20_routing_authority_decision_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_routing_authority_decision_v1.md) were confirmed:

1. `RoutingFabric` is initialized in the live advisor runtime and attached back to the connector.
   Evidence: [runtime.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/runtime.py#L281) builds `LLMConnector` without `model_router`; [runtime.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/runtime.py#L417) initializes `RoutingFabric`; [runtime.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/runtime.py#L422) attaches it to the connector.

2. Graph and report execution currently prefer `RoutingFabric` and then fall back to the API connector.
   Evidence: [graph.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/graph.py#L148) wraps `routing_fabric.get_llm_fn(...)` with API fallback; [report_graph.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/report_graph.py#L62) does the same for report writing.

3. `RoutingFabric` is not yet provider-aware concrete API execution.
   Evidence: [fabric.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/routing/fabric.py#L383) forwards API execution to the connector itself; [llm_connector.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/llm_connector.py#L304) then resolves `route.api_only()` and falls back further inside `_select_model()`.

4. `ModelRouter` is optional and not injected into the live advisor runtime.
   Evidence: [llm_connector.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/llm_connector.py#L94) makes `model_router` optional; [runtime.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/runtime.py#L281) does not pass it; repository grep did not find a live advisor-runtime injection path.

5. `routing_engine` is not part of the current advisor runtime composition root.
   Evidence: repository grep found `routing_engine` in tests and legacy/parallel code, but not in the runtime assembly path that builds the live advisor services.

## Findings

### 1. The document understates ingress lane authority because `/v3/agent/turn` is itself a live routing layer

The document defines ingress lane routing in [2026-03-20_routing_authority_decision_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_routing_authority_decision_v1.md#L21) as `/v2/advisor/ask` plus `_ROUTE_TO_EXECUTION` and `ControllerEngine.ask(route_mapping=...)`.

That is incomplete relative to the current live public entry surface.

- [runbook.md](/vol1/1000/projects/ChatgptREST/docs/runbook.md#L714) says real live asks should go through `/v3/agent/turn` or `advisor_agent_turn`, not low-level direct job submission.
- [server.py](/vol1/1000/projects/ChatgptREST/chatgptrest/mcp/server.py#L3960) defines `advisor_agent_turn`, and [server.py](/vol1/1000/projects/ChatgptREST/chatgptrest/mcp/server.py#L3992) posts it to `/v3/agent/turn`.
- [agent_mcp.py](/vol1/1000/projects/ChatgptREST/chatgptrest/mcp/agent_mcp.py#L718) exposes the same high-level turn tool, and [agent_mcp.py](/vol1/1000/projects/ChatgptREST/chatgptrest/mcp/agent_mcp.py#L788) also posts to `/v3/agent/turn`.

`/v3/agent/turn` is not a thin pass-through either.

- [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L1258) sends `goal_hint=image` directly to `gemini_web.generate_image`.
- [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L1310) sends `consult` / `dual_review` into consultation fan-out.
- [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L1362) sends Gemini research hints directly to `gemini_web.ask`.
- only the fallback branch at [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L1423) enters `ControllerEngine.ask(...)`.

Impact:

- current lane authority is not centralized in `/v2/advisor/ask`
- the main public front door still contains its own live dispatch logic

Required correction:

- either scope the document down explicitly to the `advisor_ask/controller` lane, or
- add `/v3/agent/turn` as a separate ingress lane-routing authority

### 2. There is still a duplicated route-mapping authority, not one single source

The document treats `_ROUTE_TO_EXECUTION` as the ingress lane mapping source in [2026-03-20_routing_authority_decision_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_routing_authority_decision_v1.md#L110).

That is not the only active mapping copy.

- `/v2/advisor/ask` uses the module-level `_ROUTE_TO_EXECUTION` table in [routes_advisor_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor_v3.py#L43).
- `/v3/agent/turn` redefines an inline `route_mapping` copy in [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L1424) and passes that into `ControllerEngine.ask(...)`.

This means the routing contract is not yet “three clean layers”; there is still an unresolved duplication inside layer A.

Impact:

- route-to-provider/preset/kind authority can drift between agent and advisor ingress
- the document currently presents a cleaner state than the code actually has

Required correction:

- call out the duplicated mapping explicitly as unresolved

### 3. Even inside the controller path, lane routing is broader than `_ROUTE_TO_EXECUTION + ControllerEngine.ask(route_mapping=...)`

The document states that ingress lane routing is currently decided by `_ROUTE_TO_EXECUTION` and `ControllerEngine.ask(route_mapping=...)` in [2026-03-20_routing_authority_decision_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_routing_authority_decision_v1.md#L143).

That compresses three distinct sub-decisions into one line:

- [engine.py](/vol1/1000/projects/ChatgptREST/chatgptrest/controller/engine.py#L281) calls `_plan_async_route()` first.
- [engine.py](/vol1/1000/projects/ChatgptREST/chatgptrest/controller/engine.py#L1677) shows `_plan_async_route()` runs `normalize -> kb_probe -> analyze_intent -> route_decision` and returns `route` plus `executor_lane`.
- [engine.py](/vol1/1000/projects/ChatgptREST/chatgptrest/controller/engine.py#L817) then uses `_resolve_execution_kind()` to choose `effect`, `team`, or `job`.
- only after that does [engine.py](/vol1/1000/projects/ChatgptREST/chatgptrest/controller/engine.py#L554) use `route_mapping` to convert the chosen route into `provider/preset`.

Impact:

- `_ROUTE_TO_EXECUTION` is not the lane-routing source by itself
- the controller’s graph-based route planner and execution-kind chooser are also live authority

Required correction:

- rewrite layer A as:
  - route selection: `ControllerEngine._plan_async_route()`
  - execution kind: `ControllerEngine._resolve_execution_kind()`
  - route-to-provider/preset/kind mapping: `_ROUTE_TO_EXECUTION` or equivalent ingress mapping

### 4. `RoutingFabric` is not yet proven as an active provider selector for `cc runtime`

The document says provider policy routing is what graph/report/cc runtime uses to decide which providers to try in [2026-03-20_routing_authority_decision_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_routing_authority_decision_v1.md#L24) and [2026-03-20_routing_authority_decision_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_routing_authority_decision_v1.md#L164).

The code confirms this for graph and report, but not for `cc runtime`.

- [cc_native.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/cc_native.py#L167) stores `routing_fabric`.
- the only demonstrated use is [cc_native.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/cc_native.py#L187), where `_report_routing_outcome()` reports execution outcome back to the fabric.
- repo grep found no `cc_native` path using `routing_fabric.resolve(...)` or `get_llm_fn(...)` to choose an execution provider.

Impact:

- the phrase `graph/report/cc runtime` overstates current selection coverage
- current evidence supports `graph/report` as active consumers, and `cc` as an observer/feedback producer

Required correction:

- narrow the provider-policy statement to graph/report plus any verified runtime consumers
- mention `cc_native` as currently feeding feedback, not clearly consuming provider selection

## Minimal Correction Set For v2

If this decision document is revised, the minimum safe fixes are:

1. Add `/v3/agent/turn` as a first-class ingress routing surface.
2. Call out the duplicated route-mapping table between `routes_advisor_v3` and `routes_agent_v3`.
3. Split controller lane routing into:
   - graph-based route planning
   - execution-kind selection
   - route-to-provider/preset/kind mapping
4. Narrow the `RoutingFabric` provider-policy claim so it does not overstate `cc runtime`.

## Bottom Line

`routing_authority_decision_v1` correctly fixed the earlier mistake of treating `RoutingFabric`, `ModelRouter`, and concrete API execution as one layer.

Its remaining weakness is that layer A is still too compressed:

- it centers `/v2/advisor/ask`
- it hides the controller’s internal route planner
- it omits `/v3/agent/turn`
- it omits the duplicated route-mapping copy

That means the document is a strong intermediate correction, but not yet the final routing authority contract. It should be superseded by a `routing_authority_decision_v2` before `front_door_contract_v1` is written on top of it.
