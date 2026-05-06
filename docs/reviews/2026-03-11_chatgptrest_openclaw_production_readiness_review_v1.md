# 2026-03-11 ChatgptREST + OpenClaw Production Readiness Review v1

## Verdict

**Current verdict: No-Go for formal production launch.**

The integrated ChatgptREST + OpenClaw stack is functional in a trusted local loopback setup, but it is not yet production-ready for a formal launch with restart safety, hardened auth, stable identity/provenance, and predictable control-plane behavior.

The main reason is not a single crashing bug. The problem is that several control-plane, auth, identity, and runtime-configuration gaps stack together. In a real launch, these gaps create failure modes that are hard to detect, hard to attribute, and in some cases unsafe.

## Scope

This review covers:

- ChatgptREST repo code and docs under `/vol1/1000/projects/ChatgptREST`
- OpenClaw upstream code under `/vol1/1000/projects/openclaw`
- Active OpenClaw runtime config under `/vol1/1000/home-yuanhaizhou/.home-codex-official/.openclaw/openclaw.json`
- Existing live verification evidence in [openclaw_openmind_verifier_lean_20260310.md](/vol1/1000/projects/ChatgptREST/docs/reviews/openclaw_openmind_verifier_lean_20260310.md)
- Targeted regression suite in ChatgptREST:
  `tests/test_openclaw_adapter.py`
  `tests/test_openclaw_cognitive_plugins.py`
  `tests/test_verify_openclaw_openmind_stack.py`
  `tests/test_openclaw_orch_agent.py`
  `tests/test_openclaw_guardian_issue_sweep.py`
  `tests/test_advisor_api.py`
  `tests/test_advisor_orchestrate_api.py`
  `tests/test_cognitive_api.py`
  `tests/test_role_pack.py`
  `tests/test_openmind_memory_business_flow.py`
  `tests/test_advisor_v3_end_to_end.py`

## What Is Working

- The targeted ChatgptREST regression suite above passed in this review run.
- The latest completed live verifier evidence shows the lean OpenClaw topology, OpenMind tool exposure, loopback bind, and gateway token mode all working on 2026-03-10: [openclaw_openmind_verifier_lean_20260310.md](/vol1/1000/projects/ChatgptREST/docs/reviews/openclaw_openmind_verifier_lean_20260310.md).
- OpenClaw memory/advisor/graph/telemetry plugins are packaged, loadable, and covered by basic package/source tests: [test_openclaw_cognitive_plugins.py:21](/vol1/1000/projects/ChatgptREST/tests/test_openclaw_cognitive_plugins.py#L21), [test_openclaw_cognitive_plugins.py:57](/vol1/1000/projects/ChatgptREST/tests/test_openclaw_cognitive_plugins.py#L57).

Those positives matter, but they do not offset the blockers below.

## P0 Blockers

### Current live verification is failing right now, not just historically “at risk”

- A fresh verifier run on 2026-03-11 failed **23 of 47** checks: [2026-03-11_openclaw_openmind_live_verifier_summary_v1.md](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-03-11_openclaw_openmind_live_verifier_summary_v1.md).
- Failures include OpenMind probe/tool round, memory capture/recall, role recall scoping, and negative runtime probes: [2026-03-11_openclaw_openmind_live_verifier_summary_v1.md:14](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-03-11_openclaw_openmind_live_verifier_summary_v1.md#L14).
- The failure pattern is not random noise: the runtime is often replying with generic conversational text while the verifier cannot correlate the expected tool round back to transcript state: [2026-03-11_openclaw_openmind_live_verifier_summary_v1.md:39](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-03-11_openclaw_openmind_live_verifier_summary_v1.md#L39).

Why this blocks launch:

- This is no longer only a “design might fail later” review.
- The current runtime has already drifted away from the previously passing 2026-03-10 verifier baseline.
- Whether the root cause is prompt drift, transcript correlation drift, runtime state contamination, or tool-routing regression, the chain is not stable enough to launch.

### 1. `GET /v1/advisor/runs/{run_id}` is not read-only and can dispatch new work

- The read endpoint calls `_reconcile_run_status()` inside a write transaction: [routes_advisor.py:1347](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor.py#L1347).
- `_reconcile_run_status()` can dispatch a retry job when a gate fails: [routes_advisor.py:517](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor.py#L517), [routes_advisor.py:663](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor.py#L663).

Why this blocks launch:

- A read path must not mutate workflow state or create billable follow-up work.
- Monitoring, dashboards, or repeated polling can change outcome, consume capacity, and complicate incident reconstruction.

### 2. ChatgptREST auth and OpenMind/OpenClaw plugin auth are inconsistent

- ChatgptREST global middleware requires `Authorization: Bearer ...` when `CHATGPTREST_API_TOKEN` or `CHATGPTREST_OPS_TOKEN` is configured: [app.py:34](/vol1/1000/projects/ChatgptREST/chatgptrest/api/app.py#L34), [app.py:53](/vol1/1000/projects/ChatgptREST/chatgptrest/api/app.py#L53).
- OpenMind plugins only send `X-Api-Key`, not Bearer auth:
  [openmind-advisor/index.ts:42](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-advisor/index.ts#L42),
  [openmind-memory/index.ts:94](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-memory/index.ts#L94),
  [openmind-graph/index.ts:43](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-graph/index.ts#L43),
  [openmind-telemetry/index.ts:86](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-telemetry/index.ts#L86).
- Guardian has the same problem and calls protected endpoints without auth headers: [openclaw_guardian_run.py:91](/vol1/1000/projects/ChatgptREST/ops/openclaw_guardian_run.py#L91), [openclaw_guardian_run.py:208](/vol1/1000/projects/ChatgptREST/ops/openclaw_guardian_run.py#L208), [openclaw_guardian_run.py:818](/vol1/1000/projects/ChatgptREST/ops/openclaw_guardian_run.py#L818).

Why this blocks launch:

- The current setup forces a bad choice:
  either keep the global API token off and leave the wider API surface under-protected,
  or turn it on and break OpenMind plugin traffic plus guardian automation.
- This is a hard integration fault, not just documentation debt.

### 3. `/v2/advisor/ask` idempotency is collision-prone across sessions, users, and contexts

- When clients do not pass `idempotency_key`, the route derives it from `sha256(question) + minute bucket`: [routes_advisor_v3.py:1186](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor_v3.py#L1186), [routes_advisor_v3.py:1190](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor_v3.py#L1190).
- The OpenClaw advisor plugin does not pass any `idempotency_key`, and in `ask` mode it also does not pass session identity: [openmind-advisor/index.ts:117](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-advisor/index.ts#L117), [openmind-advisor/index.ts:142](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-advisor/index.ts#L142).

Why this blocks launch:

- Two different callers asking the same question within the same minute can collide onto one job.
- The collision key ignores `role_id`, user identity, session identity, and context.
- In a formal launch, this is a correctness and data-isolation problem, not just an idempotency quality issue.

### 4. OpenClaw memory provenance is still partial in the real runtime

- OpenClaw hook context only exposes `agentId`, `sessionKey`, `workspaceDir`, and `messageProvider`: [plugins/types.ts:315](/vol1/1000/projects/openclaw/src/plugins/types.ts#L315).
- The runtime passes only those fields into `before_agent_start`: [attempt.ts:724](/vol1/1000/projects/openclaw/src/agents/pi-embedded-runner/run/attempt.ts#L724).
- But the OpenMind memory plugin expects `ctx.sessionId` and `ctx.agentAccountId` in both tool and hook paths: [openmind-memory/index.ts:257](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-memory/index.ts#L257), [openmind-memory/index.ts:293](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-memory/index.ts#L293), [openmind-memory/index.ts:351](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-memory/index.ts#L351), [openmind-memory/index.ts:384](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-memory/index.ts#L384).
- The latest completed live verifier still records `identity_gaps` and `provenance_quality: "partial"` for memory capture and recall: [openclaw_openmind_verifier_lean_20260310.md:38](/vol1/1000/projects/ChatgptREST/docs/reviews/openclaw_openmind_verifier_lean_20260310.md#L38), [openclaw_openmind_verifier_lean_20260310.md:41](/vol1/1000/projects/ChatgptREST/docs/reviews/openclaw_openmind_verifier_lean_20260310.md#L41), [openclaw_openmind_verifier_lean_20260310.md:111](/vol1/1000/projects/ChatgptREST/docs/reviews/openclaw_openmind_verifier_lean_20260310.md#L111).

Why this blocks launch:

- Durable memory is part of the product promise.
- Right now the integration works, but not with production-grade identity lineage.
- That is acceptable for local experimentation, not for formal launch.

### 5. The active OpenClaw runtime config is incompatible with the current schema, so restart safety is broken

- The active config contains keys that the current schema does not accept, including:
  `tools.sessions.visibility`: [openclaw.json:43](/vol1/1000/home-yuanhaizhou/.home-codex-official/.openclaw/openclaw.json#L43), while `ToolsSchema` has no `sessions` object: [zod-schema.agent-runtime.ts:483](/vol1/1000/projects/openclaw/src/config/zod-schema.agent-runtime.ts#L483).
  top-level `acp`: [openclaw.json:54](/vol1/1000/home-yuanhaizhou/.home-codex-official/.openclaw/openclaw.json#L54), while `OpenClawSchema` has no `acp` section: [zod-schema.ts:94](/vol1/1000/projects/openclaw/src/config/zod-schema.ts#L94).
  binding `type`: [openclaw.json:254](/vol1/1000/home-yuanhaizhou/.home-codex-official/.openclaw/openclaw.json#L254), while bindings only accept `agentId` and `match`: [zod-schema.agents.ts:14](/vol1/1000/projects/openclaw/src/config/zod-schema.agents.ts#L14).
  `agents.defaults.subagents.runTimeoutSeconds`: [openclaw.json:332](/vol1/1000/home-yuanhaizhou/.home-codex-official/.openclaw/openclaw.json#L332), while subagents schema accepts only `allowAgents`, `model`, and `thinking`: [zod-schema.agent-runtime.ts:460](/vol1/1000/projects/openclaw/src/config/zod-schema.agent-runtime.ts#L460).
  `heartbeat.lightContext`: [openclaw.json:368](/vol1/1000/home-yuanhaizhou/.home-codex-official/.openclaw/openclaw.json#L368), while heartbeat schema does not define it: [zod-schema.agent-runtime.ts:11](/vol1/1000/projects/openclaw/src/config/zod-schema.agent-runtime.ts#L11).
- Gateway startup hard-fails on invalid config snapshots: [server.impl.ts:193](/vol1/1000/projects/openclaw/src/gateway/server.impl.ts#L193).

Why this blocks launch:

- This means the current runtime may work only as long as it is not forced through a clean restart on the current code.
- A formal launch cannot depend on “do not restart” as an operating assumption.

### 6. Secrets are stored in plaintext in the active OpenClaw runtime config

- Gateway token is stored directly in runtime config: [openclaw.json:16](/vol1/1000/home-yuanhaizhou/.home-codex-official/.openclaw/openclaw.json#L16).
- OpenMind API keys are stored directly in plugin config: [openclaw.json:116](/vol1/1000/home-yuanhaizhou/.home-codex-official/.openclaw/openclaw.json#L116), [openclaw.json:140](/vol1/1000/home-yuanhaizhou/.home-codex-official/.openclaw/openclaw.json#L140), [openclaw.json:161](/vol1/1000/home-yuanhaizhou/.home-codex-official/.openclaw/openclaw.json#L161).
- Feishu and DingTalk app secrets are stored directly in runtime config: [openclaw.json:224](/vol1/1000/home-yuanhaizhou/.home-codex-official/.openclaw/openclaw.json#L224), [openclaw.json:242](/vol1/1000/home-yuanhaizhou/.home-codex-official/.openclaw/openclaw.json#L242).

Why this blocks launch:

- This may be tolerable for a single-user lab box.
- It is not acceptable as a formal production baseline without a secret-management decision and hardening standard.

### 7. Public `/v2/advisor/*` ingress currently exposes a large control-plane surface behind one API key

- The v3 router publishes not only `/advise`, `/ask`, and `/health`, but also internal/statistical and `cc-*` execution endpoints: [routes_advisor_v3.py:238](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor_v3.py#L238), [routes_advisor_v3.py:598](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor_v3.py#L598), [routes_advisor_v3.py:712](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor_v3.py#L712), [routes_advisor_v3.py:1150](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor_v3.py#L1150).
- The nginx sample forwards the whole `/v2/advisor/` prefix: [nginx_openmind.conf:21](/vol1/1000/projects/ChatgptREST/ops/nginx_openmind.conf#L21).

Why this blocks launch:

- A public ingress should expose the minimum stable API surface.
- Right now, one API key protects both public-style endpoints and internal control-plane endpoints.

## P1 High-Risk Gaps

### 8. `openclaw_mcp_url` is request-pass-through with no allowlist or loopback enforcement

- Advisor orchestration accepts `openclaw_mcp_url` as a passthrough request option: [routes_advisor.py:823](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor.py#L823), [routes_advisor.py:833](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor.py#L833).
- It is used directly to build an `OpenClawAdapter`: [advisor_orchestrate.py:149](/vol1/1000/projects/ChatgptREST/chatgptrest/executors/advisor_orchestrate.py#L149).
- The MCP HTTP client only bypasses proxies for loopback; it does not forbid non-loopback targets: [mcp_http_client.py:27](/vol1/1000/projects/ChatgptREST/chatgptrest/integrations/mcp_http_client.py#L27), [mcp_http_client.py:36](/vol1/1000/projects/ChatgptREST/chatgptrest/integrations/mcp_http_client.py#L36).

Impact:

- This is an SSRF and egress-control hole if untrusted callers can reach orchestration.

### 9. OpenClaw plugin HTTP handlers are executed before core API handlers and have no central auth gate

- Plugin HTTP routes are dispatched by `createGatewayPluginRequestHandler()` with no auth input: [plugins-http.ts:12](/vol1/1000/projects/openclaw/src/gateway/server/plugins-http.ts#L12).
- In the main HTTP request order, plugin requests run before OpenAI-compatible handlers: [server-http.ts:327](/vol1/1000/projects/openclaw/src/gateway/server-http.ts#L327), [server-http.ts:350](/vol1/1000/projects/openclaw/src/gateway/server-http.ts#L350), [server-http.ts:353](/vol1/1000/projects/openclaw/src/gateway/server-http.ts#L353).
- Route collisions are only recorded as diagnostics during registration: [registry.ts:310](/vol1/1000/projects/openclaw/src/plugins/registry.ts#L310).

Impact:

- A plugin can shadow or extend HTTP surface without going through the same auth and product-contract controls as the core gateway.

### 10. Plugin failures are mostly fail-open

- Gateway plugin diagnostics are logged but do not stop startup: [server-plugins.ts:17](/vol1/1000/projects/openclaw/src/gateway/server-plugins.ts#L17), [server-plugins.ts:30](/vol1/1000/projects/openclaw/src/gateway/server-plugins.ts#L30).
- Plugin service start failures are logged and swallowed: [services.ts:53](/vol1/1000/projects/openclaw/src/plugins/services.ts#L53).
- Hook runner is initialized with `catchErrors: true`: [hook-runner-global.ts:21](/vol1/1000/projects/openclaw/src/plugins/hook-runner-global.ts#L21), [hook-runner-global.ts:29](/vol1/1000/projects/openclaw/src/plugins/hook-runner-global.ts#L29).
- Hook execution defaults to catch-and-continue: [hooks.ts:93](/vol1/1000/projects/openclaw/src/plugins/hooks.ts#L93), [hooks.ts:95](/vol1/1000/projects/openclaw/src/plugins/hooks.ts#L95).

Impact:

- Required integration components can silently degrade while the system appears healthy.

### 11. Health checks are too shallow and can report false green

- `/healthz` only checks SQLite connectivity: [routes_jobs.py:945](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_jobs.py#L945).
- `/v1/ops/status` reports DB-derived counters and `ui_canary` summary, but not driver/MCP/OpenClaw/Chrome liveness directly: [routes_ops.py:489](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_ops.py#L489), [routes_ops.py:524](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_ops.py#L524).

Impact:

- API can look “healthy” while the actual prompt path is broken.

### 12. `/v2/advisor/ask` bypasses the stricter v1 write-path guardrails

- `/v1/advisor/advise` enforces client allowlist and trace headers when executing: [routes_advisor.py:1243](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor.py#L1243).
- `/v2/advisor/ask` creates jobs directly via `create_job()` and sets client metadata internally, without reusing the v1 guard path: [routes_advisor_v3.py:1381](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor_v3.py#L1381), [routes_advisor_v3.py:1405](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor_v3.py#L1405).

Impact:

- Write-path attribution and policy are inconsistent between adjacent APIs.

### 13. `advisor_ask` leaks internal traceback text on job-creation failure

- On failure it returns a `502` including the last 500 characters of traceback: [routes_advisor_v3.py:1420](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor_v3.py#L1420).

Impact:

- This is avoidable internal detail exposure on an external API.

### 14. OpenClaw `advise` mode is not session-aware and the v3 `/advise` route drops much of the request context anyway

- The OpenClaw advisor plugin does not consume runtime context and hardcodes `session_id: ""` and `user_id: "openclaw"` in `advise` mode: [openmind-advisor/index.ts:108](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-advisor/index.ts#L108), [openmind-advisor/index.ts:125](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-advisor/index.ts#L125).
- The `/v2/advisor/advise` route extracts only `message` and `role_id`, then calls `api.advise(msg)` without passing `session_id`, `user_id`, or `context`: [routes_advisor_v3.py:239](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor_v3.py#L239), [routes_advisor_v3.py:246](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor_v3.py#L246), [routes_advisor_v3.py:265](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor_v3.py#L265).
- `AdvisorAPI.advise()` supports forwarding `user_id` and `session_id` when kwargs are passed: [advisor_api.py:83](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/advisor_api.py#L83), [advisor_api.py:97](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/advisor_api.py#L97), [advisor_api.py:109](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/advisor_api.py#L109).

Impact:

- The integration is missing stable per-session attribution for one of its advertised paths.

## P2 Medium-Risk Gaps

### 15. v2 rate limiting is in-memory and per-process only

- Advisor v3 limiter is a local dict/list in process memory: [routes_advisor_v3.py:88](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor_v3.py#L88).
- Cognitive API uses the same pattern: [routes_cognitive.py:168](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_cognitive.py#L168).

Impact:

- Multi-worker deployment and restart behavior are inconsistent.

### 16. v3 trace storage is in-memory only

- `TraceStore` is in-memory and the source comment says production should use SQLite or EventBus: [advisor_api.py:22](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/advisor_api.py#L22), [advisor_api.py:25](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/advisor_api.py#L25).

Impact:

- `/v2/advisor/trace/*` is not durable across restarts.

### 17. v3 router load failure can be silently downgraded into a partially missing API

- `create_app()` wraps v3 router load in `try/except` and only logs a warning: [app.py:66](/vol1/1000/projects/ChatgptREST/chatgptrest/api/app.py#L66).
- A simple config parse failure such as invalid `OPENMIND_RATE_LIMIT` can trigger this path: [routes_advisor_v3.py:91](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor_v3.py#L91).

Impact:

- Production can boot in a partially degraded mode without hard failing deployment.

### 18. Systemd/runbook drift is still present in ops assets

- `runbook.md` says `orch-doctor` runs `--reconcile`, but the service unit does not: [runbook.md:559](/vol1/1000/projects/ChatgptREST/docs/runbook.md#L559), [chatgptrest-orch-doctor.service:19](/vol1/1000/projects/ChatgptREST/ops/systemd/chatgptrest-orch-doctor.service#L19).
- Some units still hardcode local user paths or repo paths: [chatgptrest-guardian.service:17](/vol1/1000/projects/ChatgptREST/ops/systemd/chatgptrest-guardian.service#L17), [chatgptrest-controller-lanes.service:7](/vol1/1000/projects/ChatgptREST/ops/systemd/chatgptrest-controller-lanes.service#L7).
- The env example documents ChatgptREST tokens but does not give a clear OpenMind auth template for `/v2`: [chatgptrest.env.example:39](/vol1/1000/projects/ChatgptREST/ops/systemd/chatgptrest.env.example#L39).

Impact:

- Deployability and day-2 operations are still environment-fragile.

### 19. Current OpenClaw plugin packaging and test coverage are not strong enough for release confidence

- Plugin tests are mostly package/file presence and string assertions against source text: [test_openclaw_cognitive_plugins.py:21](/vol1/1000/projects/ChatgptREST/tests/test_openclaw_cognitive_plugins.py#L21), [test_openclaw_cognitive_plugins.py:57](/vol1/1000/projects/ChatgptREST/tests/test_openclaw_cognitive_plugins.py#L57).
- They do not prove runtime contract compatibility with the current OpenClaw hook context.
- Plugin installs are path-based in the active runtime config, not release-pinned artifacts: [openclaw.json:186](/vol1/1000/home-yuanhaizhou/.home-codex-official/.openclaw/openclaw.json#L186).

Impact:

- This makes the integration harder to reproduce and easier to drift silently.

### 20. Current OpenClaw runtime is configured as lean single-agent, not full orchestration

- Cross-agent sends are forbidden when `tools.agentToAgent.enabled=false`: [openclaw.json:39](/vol1/1000/home-yuanhaizhou/.home-codex-official/.openclaw/openclaw.json#L39), [sessions-send-tool.ts:230](/vol1/1000/projects/openclaw/src/agents/tools/sessions-send-tool.ts#L230).

Impact:

- If the intended launch goal is “OpenClaw as a full multi-agent orchestration runtime”, the current runtime profile is not there yet.
- If the intended launch goal is “lean single main agent with OpenMind substrate”, this is not itself a blocker.

## Launch Decision By Layer

### ChatgptREST core queue

Status: **conditionally launchable only for a trusted internal loopback setup**

Reasons:

- Core queueing and targeted tests are in decent shape.
- But formal launch is blocked by write-path inconsistency, read-side effects, shallow health checks, and orchestration pass-through risk.

### OpenMind v2/v3 API surface

Status: **not ready for external or semi-external formal launch**

Reasons:

- Auth model is inconsistent.
- Public surface is broader than it should be.
- `/ask` idempotency design is unsafe for multi-session or multi-client usage.
- Provenance and trace durability are incomplete.

### OpenClaw runtime

Status: **not ready for formal production launch on the current runtime image/config**

Reasons:

- Restart safety is not assured because current config is schema-invalid.
- Secrets are still stored in plaintext runtime JSON.
- Plugin HTTP and plugin failure semantics are not hardened enough.

## Required Before Go-Live

These are the minimum changes I would require before approving launch:

1. Make all read endpoints read-only.
   Specifically remove retry/job-dispatch side effects from `GET /v1/advisor/runs/{run_id}`.

2. Unify auth for ChatgptREST v1, OpenMind v2, and OpenClaw plugins.
   Pick one supported production contract and make guardian/plugins follow it.

3. Redesign `/v2/advisor/ask` idempotency.
   Require caller-supplied idempotency keys or include session/user/role/context identity in server-generated keys.

4. Fix OpenClaw memory identity propagation end-to-end.
   Runtime hook context, plugin code, and verifier expectations must agree.

5. Migrate the active OpenClaw runtime config to the current schema and prove clean restart.
   This must be validated on the current commit, not assumed from an older running process.

6. Remove plaintext secrets from `openclaw.json` and define secret-loading policy.

7. Shrink public ingress exposure.
   Only expose stable public endpoints; keep `cc-*` and control-plane routes internal.

8. Add real readiness checks.
   Include at least API, worker, driver, OpenClaw gateway, and Chrome/MCP path health.

9. Add production-meaningful integration tests.
   At minimum:
   - API token + X-Api-Key coexistence
   - OpenClaw plugin auth against protected ChatgptREST
   - hook-context identity propagation
   - advisor `/ask` idempotency isolation across sessions
   - clean restart with current runtime config

10. Re-run live verification after all fixes and keep the evidence bundle.

## Bottom Line

The stack is already beyond prototype quality. It has real working pieces, and the historical live verifier proves the main loop can run.

But for a formal launch decision, the answer is still **no**.

The biggest remaining gaps are:

- control-plane safety
- auth consistency
- identity/provenance correctness
- restart safety
- secret hygiene

Once those are fixed and re-verified live, this can move from “works on the maintainer host” to “production-ready system.”
