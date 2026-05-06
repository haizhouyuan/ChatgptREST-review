# 2026-03-20 Authority Matrix Verification v1

## Scope

Target under verification:

- [2026-03-20_authority_matrix_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_authority_matrix_v1.md)

Verification method on `2026-03-20`:

- re-read the target document
- re-check live `systemd` status and effective units
- re-count the cited SQLite stores
- re-check ingress routes and path helpers in code
- re-check runtime composition root instead of relying only on design docs

## Verdict

`authority_matrix_v1` is directionally strong but not yet safe to freeze as the canonical authority document.

The core substrate facts were verified:

- `openclaw-gateway.service=active`, while `chatgptrest-api.service`, `chatgptrest-mcp.service`, and `chatgptrest-feishu-ws.service` are `inactive`
- `state/jobdb.sqlite3` counts match exactly: `jobs=7924`, `controller_runs=130`, `advisor_runs=201`
- `data/evomap_knowledge.db` counts match exactly: `documents=7863`, `atoms=99493`, `edges=90611`
- the current OpenClaw plugin bridge really posts to `/v3/agent/turn`
- Feishu WS really defaults to `/v2/advisor/advise`
- the HOME-relative OpenMind stores are currently very thin

But four authority statements are materially incomplete or overstated, so this document should be treated as `partially verified`, not frozen `A1`.

## Confirmed

The following parts of [2026-03-20_authority_matrix_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_authority_matrix_v1.md) were confirmed by direct re-check:

1. The live runtime substrate is currently OpenClaw, not the ChatgptREST API host.
   Evidence: `systemctl --user is-active` returned `active / inactive / inactive / inactive` for `openclaw-gateway.service`, `chatgptrest-api.service`, `chatgptrest-mcp.service`, and `chatgptrest-feishu-ws.service`.

2. The effective live HOME for the gateway is `/home/yuanhaizhou/.home-codex-official`.
   Evidence: `systemctl --user cat openclaw-gateway.service` shows `Environment=HOME=/home/yuanhaizhou/.home-codex-official`.

3. The execution ledger and artifact root are effectively repo-local.
   Evidence: the active drop-ins on `chatgptrest-api.service` override `CHATGPTREST_DB_PATH` and `CHATGPTREST_ARTIFACTS_DIR` to `/vol1/1000/projects/ChatgptREST/state/jobdb.sqlite3` and `/vol1/1000/projects/ChatgptREST/artifacts`.

4. The OpenClaw slow-path bridge really uses `/v3/agent/turn`.
   Evidence: [index.ts](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-advisor/index.ts#L243) describes the tool as calling the public `/v3/agent/turn` API directly, and [index.ts](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-advisor/index.ts#L306) posts to `"/v3/agent/turn"`.

5. Feishu still points at `/v2/advisor/advise`.
   Evidence: [feishu_ws_gateway.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/feishu_ws_gateway.py#L41) resolves its default API URL to `/v2/advisor/advise`, and [chatgptrest-feishu-ws.service](/vol1/1000/projects/ChatgptREST/ops/systemd/chatgptrest-feishu-ws.service#L11) hard-codes the same URL.

6. Telemetry path clarity vs runtime breakage is real.
   Evidence: the route exists under `/v2/telemetry/ingest`, while `journalctl --user -u openclaw-gateway.service` shows repeated `openmind-telemetry: flush failed: TypeError: fetch failed`.

## Findings

### 1. The front-door split is understated because `/v2/advisor/ask` was omitted

The matrix currently models the v2 side only as `/v2/advisor/advise` in rows 111-114 of [2026-03-20_authority_matrix_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_authority_matrix_v1.md#L111).

That is incomplete.

- [routes_advisor_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor_v3.py#L1573) defines `POST /v2/advisor/ask` as a unified intelligent ask entrypoint.
- [routes_advisor_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor_v3.py#L1579) explicitly states this is the endpoint behind the `chatgptrest_advisor_ask` MCP tool.
- [server.py](/vol1/1000/projects/ChatgptREST/chatgptrest/mcp/server.py#L1942) defines `chatgptrest_advisor_ask`, and [server.py](/vol1/1000/projects/ChatgptREST/chatgptrest/mcp/server.py#L1985) posts it to `/v2/advisor/ask`.

Impact:

- the current front-door split is at least three-way: `/v3/agent/turn`, `/v2/advisor/advise`, and `/v2/advisor/ask`
- any downstream `front_door_contract_v1` built only from `turn vs advise` will miss a live ingress that is still wired and tested

Required correction:

- add a separate authority row for `/v2/advisor/ask`, likely `A2 Provisional Live` or `U Unresolved`

### 2. The EvoMap row conflates the repo-local knowledge DB with a separate HOME-relative runtime signals DB

Row 106 of [2026-03-20_authority_matrix_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_authority_matrix_v1.md#L106) labels `/vol1/1000/projects/ChatgptREST/data/evomap_knowledge.db` as `EvoMap runtime graph DB`.

The repo-local knowledge DB is real, but it is not the only EvoMap runtime store.

- [openmind_paths.py](/vol1/1000/projects/ChatgptREST/chatgptrest/core/openmind_paths.py#L54) resolves the repo-local knowledge DB through `resolve_evomap_knowledge_runtime_db_path()`.
- [evomap/paths.py](/vol1/1000/projects/ChatgptREST/chatgptrest/evomap/paths.py#L9) separately resolves `resolve_evomap_db_path()` to `~/.openmind/evomap/signals.db` by default.
- [runtime.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/runtime.py#L278) builds `EvoMapObserver` from `resolve_evomap_db_path()`.
- [runtime.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/runtime.py#L366) independently builds the knowledge DB from `resolve_evomap_knowledge_runtime_db_path()`.

Live re-check confirmed both files exist:

- `/vol1/1000/projects/ChatgptREST/data/evomap_knowledge.db` is large and populated
- `/home/yuanhaizhou/.home-codex-official/.openmind/evomap/signals.db` also exists, even though it is currently thin

Impact:

- the matrix currently freezes only the knowledge DB side of EvoMap
- it leaves the runtime observer / team-scorecard / signals authority implicit, which is exactly the kind of hidden split-brain the matrix was supposed to eliminate

Required correction:

- rename row 106 to `EvoMap knowledge DB`, or
- add a second row for `EvoMap signals DB` and classify it separately

### 3. The routing row overstates `ModelRouter` as a live co-authority in the current advisor runtime

Rows 115-116 of [2026-03-20_authority_matrix_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_authority_matrix_v1.md#L115) say routing authority is still `RoutingFabric + ModelRouter + LLMConnector static fallback`, and the actual API invocation chain is `RoutingFabric -> ModelRouter -> static route map -> Gemini/MiniMax fallback`.

That is too strong for the current runtime composition root.

- [llm_connector.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/llm_connector.py#L88) accepts `model_router` only as an optional constructor dependency.
- [runtime.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/runtime.py#L281) constructs `LLMConnector(...)` without passing `model_router=...`.
- [runtime.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/runtime.py#L417) initializes `RoutingFabric` and only attaches that fabric back to the connector.
- repository grep found no advisor runtime path that instantiates `ModelRouter` and injects it into the live connector.

`ModelRouter` is therefore a dormant code path here, not a verified live authority in the current advisor runtime.

Impact:

- the document currently mixes `implemented possibility` with `live composition root`
- that makes the routing authority look more plural than the current runtime wiring actually is

Required correction:

- change the current-runtime statement to `RoutingFabric + LLMConnector static/API fallback`, and
- mention `ModelRouter` as existing but not wired into the current advisor runtime

### 4. The session-truth row misses the public-facade durable session store

Row 117 of [2026-03-20_authority_matrix_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_authority_matrix_v1.md#L117) describes unresolved session truth as `OpenClaw session + ChatgptREST job/controller ledger`.

That is incomplete because `/v3/agent/*` has its own persisted facade session store.

- [agent_session_store.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/agent_session_store.py#L19) resolves the public agent session store from `CHATGPTREST_AGENT_SESSION_DIR`, else from `CHATGPTREST_DB_PATH` parent plus `agent_sessions`.
- [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L968) instantiates that store at router initialization time.
- [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L992) writes session state into that store.
- live repo state already contains persisted facade session files under `state/agent_sessions`.

Impact:

- session truth is not a two-ledger problem
- it is at least a three-ledger problem: OpenClaw `.openclaw`, public agent `state/agent_sessions`, and execution `state/jobdb.sqlite3`

Required correction:

- revise the session-truth row to include `state/agent_sessions` explicitly

## Minimal Correction Set For v2

If this matrix is revised, the minimum safe changes are:

1. Add `/v2/advisor/ask` as an explicit ingress row.
2. Split `EvoMap knowledge DB` from `EvoMap signals DB`.
3. Reword routing authority so `ModelRouter` is not presented as live runtime wiring unless actual injection is shown.
4. Reword session-truth so `state/agent_sessions` is called out as a first-class ledger.

## Bottom Line

`authority_matrix_v1` got the substrate, service-state, DB-thickness, and main OpenClaw bridge facts mostly right.

Its weak point is that it still compresses several multi-ledger or multi-ingress areas into single rows:

- v2 ingress
- EvoMap runtime state
- routing composition
- session truth

Because those are exactly the unresolved authority domains the document is supposed to drive next, this file should not be treated as the final freeze artifact. It should be superseded by a corrected `authority_matrix_v2` before downstream decision docs are written on top of it.
