# 2026-04-01 ChatgptREST 定位漂移代码与运行态独立复核 v1

## 范围与方法

这版复核不再以文档叙事为主，而是以以下证据为主：

1. `create_app()` 的真实挂载与 startup manifest
2. `agent_v3 / advisor_v3 / controller / jobs / cognitive / task_runtime / workspace / repo_cognition` 的代码接线
3. 当前 live runtime 的端口、健康检查与服务身份
4. 定向 pytest 的通过范围与未覆盖边界

本轮不尝试给出“理想架构蓝图”，而是回答一个更朴素的问题：

> ChatgptREST 今天在代码和运行态上到底是什么，它的主链在哪里，哪些模块已经是生产性核心，哪些还只是 foundation / scaffold。

## 核心结论

### 结论 1

`ChatgptREST` 现在在代码现实里已经不是“OpenClaw 的一个窄插件后端”。

它已经是一个单进程多平面宿主，至少同时承载了这些真实入口：

- `jobs_v1`
- `advisor_v1`
- `consult_v1`
- `issues_v1`
- `metrics_v1`
- `ops_v1`
- `evomap_v1`
- `cognitive_v2`
- `dashboard_v2`
- `advisor_v3`
- `agent_v3`
- `task_runtime_v1`

其中 `advisor_v3`、`agent_v3`、`cognitive_v2` 都在 `create_app()` 中被标为 `core=True`；`task_runtime_v1` 和 `cc_sessiond_v1` 被标为 `core=False`。见：

- `chatgptrest/api/app.py:142`
- `chatgptrest/api/app.py:156`
- `chatgptrest/api/app.py:174`
- `chatgptrest/api/app.py:185`
- `chatgptrest/api/app.py:194`

这说明“多平面宿主”不是文档夸张，而是 app 挂载现实。

### 结论 2

当前默认 northbound 面并没有物理上收敛成单一路径，而是形成了“默认入口 + 厚底层 REST 入口 + 低层 jobs 入口”的分层并存。

真实关系是：

- public MCP 默认面
  - `chatgptrest/mcp/agent_mcp.py:944`
  - `chatgptrest/mcp/agent_mcp.py:1032`
- public MCP 最终仍调用 `/v3/agent/turn`
  - `chatgptrest/mcp/agent_mcp.py:1033`
  - `chatgptrest/mcp/server.py:3945`
- `/v3/agent/turn` 本身是一个厚入口，不是薄 facade
  - 它自己处理 `task_intake`
  - 自己处理 `clarify`
  - 自己处理 `workspace_request`
  - 自己处理 `consult`
  - 自己处理 `image`
  - 自己处理 `direct gemini lane`
  - 只有部分路径才进入 `ControllerEngine.ask()`
  - 见 `chatgptrest/api/routes_agent_v3.py:2416`
  - 见 `chatgptrest/api/routes_agent_v3.py:2508`
  - 见 `chatgptrest/api/routes_agent_v3.py:2611`
  - 见 `chatgptrest/api/routes_agent_v3.py:3184`
  - 见 `chatgptrest/api/routes_agent_v3.py:3266`
  - 见 `chatgptrest/api/routes_agent_v3.py:3366`

所以代码现实不是“public MCP 已经替代了 agent_v3”，而是“public MCP 成了默认治理 wrapper，但真实执行面仍大量落在 `agent_v3` 这层厚 REST 上”。

### 结论 3

`advisor_v3` 和 `agent_v3` 并不共享同一条执行语义，它们通过 `ControllerEngine` 进入了两种不同模式：

- `advisor_v3 -> ControllerEngine.advise()` 是同步图执行
  - `chatgptrest/api/routes_advisor_v3.py:758`
  - `chatgptrest/controller/engine.py:44`
  - `chatgptrest/controller/engine.py:102`
  - `chatgptrest/controller/engine.py:121`
  - provider 被记成 `advisor_graph`
  - `chatgptrest/controller/engine.py:124`

- `agent_v3 -> ControllerEngine.ask()` 是异步控制器执行
  - `chatgptrest/api/routes_agent_v3.py:3382`
  - `chatgptrest/controller/engine.py:264`
  - 它先做 route planning
  - 再决定 `job / team / effect`
  - 再把大部分执行落到 `job_store.create_job()`
  - `chatgptrest/controller/engine.py:290`
  - `chatgptrest/controller/engine.py:509`
  - `chatgptrest/controller/engine.py:564`
  - `chatgptrest/controller/engine.py:610`

这意味着 `controller` 是中枢，但并不是单一模式中枢，而是至少承载了：

- sync advisor graph delivery
- async external job dispatch
- team child executor dispatch
- effect intent planning

如果没有单独的 authority matrix，这就很容易被体感成“越来越乱”。

更重要的是，这不只是“双入口”，而是已经出现了“同一 controller，不同入口注入不同 execution policy”的代码级分叉。

最硬的两个例子：

- `agent_v3` 给 `ControllerEngine.ask()` 传入的 `route_mapping` 包含 `analysis_heavy`，并且显式关闭 `kb_direct_completion_allowed`
  - `chatgptrest/api/routes_agent_v3.py:3367`
  - `chatgptrest/api/routes_agent_v3.py:3372`
  - `chatgptrest/api/routes_agent_v3.py:3401`
- `advisor_v3 /ask` 使用自己的 `_ROUTE_TO_EXECUTION`，没有 `analysis_heavy`，同时保留 `_kb_direct_completion_allowed(...)`
  - `chatgptrest/api/routes_advisor_v3.py:52`
  - `chatgptrest/api/routes_advisor_v3.py:84`
  - `chatgptrest/api/routes_advisor_v3.py:1976`

这意味着即使两条面都进入 `ControllerEngine.ask()`，也不保证 route execution policy 一致。

### 结论 4

`agent_v3` 里存在明确的入口治理冲突痕迹：代码一边把它保留为厚 REST 面，一边又显式禁止 coding agent 直接打这条面。

证据：

- `_DIRECT_AGENT_REST_BLOCKED_CLIENTS` 包含 `codex`、`claude-code`、`antigravity`、`chatgptrestctl`
  - `chatgptrest/api/routes_agent_v3.py:94`
- `_DIRECT_AGENT_REST_ALLOWED_CLIENTS` 只放了 `chatgptrest-mcp`、`chatgptrestctl-maint`、`openclaw-advisor`
  - `chatgptrest/api/routes_agent_v3.py:103`
- guard 报错明确要求改走 public MCP
  - `chatgptrest/api/routes_agent_v3.py:283`
  - `chatgptrest/api/routes_agent_v3.py:300`

也就是说：

- 从产品口径看，`agent_v3` 不是 coding agent 的默认入口
- 从代码实现看，`agent_v3` 却仍是默认 northbound 能力的核心承载层
- public MCP 只是把默认使用者导向它，而不是替换了它

这不是错误实现，但如果不明确写进架构 authority，就会持续制造“到底谁才是正式产品面”的混乱。

还有一个更实质的语义分叉：

- controller 把 `action` 视为 `effect_intent` + human gate
  - `chatgptrest/controller/engine.py:838`
- advisor graph 却把 `action` 路由到 `execute_funnel`
  - `chatgptrest/advisor/graph.py:1444`

所以“同名 route”在不同子系统里并不总是同一含义。

## 代码主链现实

### A. Coding Agent 默认主链

当前最接近“正式默认主链”的代码链是：

1. public MCP tool
2. `/v3/agent/turn`
3. `agent_v3` 的 contract / clarify / workspace / dispatch 逻辑
4. `ControllerEngine.ask()` 或直接 job / consult / workspace 执行
5. `jobs` 或 `team` 或 `effect` / `workspace` 子平面

关键证据：

- public MCP tool definition
  - `chatgptrest/mcp/agent_mcp.py:944`
- public MCP -> `/v3/agent/turn`
  - `chatgptrest/mcp/agent_mcp.py:1032`
  - `chatgptrest/mcp/agent_mcp.py:1033`
- `/v3/agent/turn`
  - `chatgptrest/api/routes_agent_v3.py:2416`
- workspace 直连执行
  - `chatgptrest/api/routes_agent_v3.py:2611`
- controller ask
  - `chatgptrest/api/routes_agent_v3.py:3382`

### B. Advisor / OpenMind 主链

当前最接近“OpenMind 同步问答主链”的代码链是：

1. `/v2/advisor/advise`
2. `ControllerEngine.advise()`
3. `AdvisorAPI.advise()`
4. compiled advisor graph
5. `ContextResolver` / KB / routing fabric / memory / LLM

关键证据：

- route entry
  - `chatgptrest/api/routes_advisor_v3.py:686`
  - `chatgptrest/api/routes_advisor_v3.py:758`
- controller sync advise
  - `chatgptrest/controller/engine.py:44`
  - `chatgptrest/controller/engine.py:102`
- advisor api
  - `chatgptrest/advisor/advisor_api.py:51`
  - `chatgptrest/advisor/advisor_api.py:83`
  - `chatgptrest/advisor/advisor_api.py:109`
- graph 调用 context resolver
  - `chatgptrest/advisor/graph.py:923`
  - `chatgptrest/advisor/graph.py:925`

### C. Legacy / low-level 主链

`/v1/jobs` 不是死代码。它仍然是当前权威 completion contract / canonical answer 的生产面。

关键证据：

- jobs router 真实挂载
  - `chatgptrest/api/app.py:142`
- `ControllerEngine.ask()` 仍调用 `job_store.create_job()`
  - `chatgptrest/controller/engine.py:610`
- `agent_v3` 的 image / gemini direct / consult 也仍直接走 job lane
  - `chatgptrest/api/routes_agent_v3.py:3099`
  - `chatgptrest/api/routes_agent_v3.py:3284`
  - `chatgptrest/api/routes_agent_v3.py:3185`

结论不是“jobs 已废弃”，而是“jobs 已降到低层 substrate，但仍保有完成语义权威”。

## 模块完成度判断

### 1. `agent_v3 / controller / advisor_v3`

完成度判断：高，已是生产性核心。

依据：

- 代码厚度大，不是壳
  - `chatgptrest/api/routes_agent_v3.py` 3700+ 行
  - `chatgptrest/api/routes_advisor_v3.py` 2000+ 行
  - `chatgptrest/controller/engine.py` 1900+ 行
- 定向测试全绿
  - `tests/test_api_startup_smoke.py`
  - `tests/test_routes_agent_v3.py`
  - `tests/test_routes_advisor_v3_security.py`
- `agent_v3` 测试覆盖了 session events、task intake 注入、workspace、memory capture 等北向契约
  - `tests/test_routes_agent_v3.py:27`
  - `tests/test_routes_agent_v3.py:162`
  - `tests/test_routes_agent_v3.py:206`
- `advisor_v3` 测试覆盖了 auth、rate limit、health、control key / loopback guard
  - `tests/test_routes_advisor_v3_security.py:32`
  - `tests/test_routes_advisor_v3_security.py:71`
  - `tests/test_routes_advisor_v3_security.py:90`

但要注意一个细节：

- `ControllerEngine` 支持 KB direct completion
  - `chatgptrest/controller/engine.py:397`
- `agent_v3` 却显式关闭了 KB direct completion / synthesis
  - `chatgptrest/api/routes_agent_v3.py:3401`
  - `chatgptrest/api/routes_agent_v3.py:3402`

这说明不同入口对同一 controller 施加了不同治理策略，进一步加剧“同中枢、多权威口径”的风险。

进一步说，这种策略分叉已经不是潜在风险，而是现有代码事实：

- research scenario pack 在 `thinking_heavy` 下会真实产出 `analysis_heavy`
  - `chatgptrest/advisor/scenario_packs.py:373`
  - `chatgptrest/advisor/scenario_packs.py:470`
- 进入 `agent_v3` 时，这个 route 有显式映射
  - `chatgptrest/api/routes_agent_v3.py:3372`
- 进入 `advisor_v3 /ask` 时，这个 route 会因为映射缺失而落回默认 `quick_ask`
  - `chatgptrest/controller/engine.py:564`

这说明“不同入口命中同一 route 名称时是否等价”目前并不成立。

### 2. `work_memory / cognitive`

完成度判断：高，但只对 OpenMind / public-agent 主链成立。

依据：

- live cognitive health 为 `ok`
  - `GET http://127.0.0.1:18711/v2/cognitive/health`
  - 返回 `runtime_ready=true, memory_ready=true, kb_ready=true, graph_ready=true`
- `ContextResolver` 真实读取 `WorkMemoryManager.build_active_context()`
  - `chatgptrest/cognitive/context_service.py:200`
- `MemoryCaptureService` 真实写 `WorkMemoryManager.write_from_capture()`
  - `chatgptrest/cognitive/memory_capture_service.py:184`
- `agent_v3` 自动 memory capture 已接入主链
  - `chatgptrest/api/routes_agent_v3.py:706`
- advisor graph quick ask 也会注入 `ContextResolver`
  - `chatgptrest/advisor/graph.py:923`

测试证据也强：

- `tests/test_cognitive_api.py`
- `tests/test_context_service_work_memory.py`
- `tests/test_capture_work_memory.py`

本轮点跑这些测试，均通过。

### 3. `workspace`

完成度判断：中等，接线真实，但 live 可用性当前不稳。

依据：

- `agent_v3` 在 `workspace_request` 分支中直接执行 `WorkspaceService().execute(...)`
  - `chatgptrest/api/routes_agent_v3.py:2508`
  - `chatgptrest/api/routes_agent_v3.py:2611`
- `WorkspaceService` 有五个实装 action
  - `search_drive_files`
  - `fetch_drive_file`
  - `deliver_report_to_docs`
  - `append_sheet_rows`
  - `send_gmail_notice`
  - `chatgptrest/workspace/service.py:43`
  - `chatgptrest/workspace/service.py:53`
  - `chatgptrest/workspace/service.py:97`
  - `chatgptrest/workspace/service.py:122`
  - `chatgptrest/workspace/service.py:179`
  - `chatgptrest/workspace/service.py:224`

但 live auth 当前失败：

- `WorkspaceService().auth_state()` 返回：
  - `ok: False`
  - `invalid_grant: Token has been expired or revoked.`
  - token path `/home/yuanhaizhou/.openmind/google_token.json`

测试层面：

- `tests/test_workspace_service.py` 证明 service 逻辑真实，但主要依赖 fake Google client
  - `tests/test_workspace_service.py:73`
  - `tests/test_workspace_service.py:124`
- `tests/test_workspace_outbox_handlers.py` 证明 outbox 接线存在

因此更准确的说法是：

> workspace 不是 stub，而是已接线的 side-effect / delivery plane；只是当前 live auth 失效，生产可用性未达稳态。

### 4. `repo_cognition`

完成度判断：中等，但它是治理工具层，不是 serving core。

依据：

- `generate_bootstrap_packet()` 会真实调用：
  - plane detection
  - canonical docs
  - runtime snapshot
  - GitNexus query
  - history search
  - doc obligations
  - `chatgptrest/repo_cognition/bootstrap.py:111`
- `generate_runtime_snapshot()` 真实调用 quick runtime summary / health_probe
  - `chatgptrest/repo_cognition/runtime.py:21`
- `query_gitnexus()` 是 subprocess adapter，不是空壳
  - `chatgptrest/repo_cognition/gitnexus_adapter.py:14`

我本轮实际运行：

- `python scripts/chatgptrest_bootstrap.py --task 'validate repo cognition runtime and surfaces' --runtime quick`

它确实返回了 `bootstrap-v1` JSON。

但它明显不是 serving core：

- `app.py` 没有挂 `repo_cognition` router
- 它主要通过 CLI / MCP tool / 脚本暴露
  - `scripts/chatgptrest_bootstrap.py`
  - `scripts/check_doc_obligations.py`
  - `chatgptrest/cli.py:1342`
  - `chatgptrest/mcp/agent_mcp.py:1368`
- `danger_zones` 仍留 TODO
  - `chatgptrest/repo_cognition/bootstrap.py:90`

所以它是真的、可用的治理工具层，但不应被夸大为主业务 runtime。

### 5. `task_runtime`

完成度判断：

- 作为 foundation 子系统：中高
- 作为主系统 authoritative runtime：低到中

依据：

- app 中 `core=False`
  - `chatgptrest/api/app.py:194`
- 公开 API 只做到建任务、查状态、resume、signal、operator approve/reject/rollback
  - `chatgptrest/task_runtime/api_routes.py`
- `TaskInitializer` context snapshot 仍写明 `for now`
  - `chatgptrest/task_runtime/task_initializer.py:143`
- `PromotionService` graders 和 artifact refs 仍是 placeholder
  - `chatgptrest/task_runtime/promotion_service.py:246`
  - `chatgptrest/task_runtime/promotion_service.py:257`
  - `chatgptrest/task_runtime/promotion_service.py:268`
  - `chatgptrest/task_runtime/promotion_service.py:315`
- `delivery_integration.py` 明确自称 scaffold，且写明尚未生成 authoritative `completion_contract / canonical_answer`
  - `chatgptrest/task_runtime/delivery_integration.py:1`
  - `chatgptrest/task_runtime/delivery_integration.py:91`
- `memory_distillation.py` 明确自称 scaffold，且尚未接入 real work-memory manager / review lanes
  - `chatgptrest/task_runtime/memory_distillation.py:1`
  - `chatgptrest/task_runtime/memory_distillation.py:34`

测试边界也说明了这一点：

- `tests/test_task_runtime.py` 路由端到端只断言创建后 `status == frozen`
  - `tests/test_task_runtime.py:154`
  - `tests/test_task_runtime.py:174`
- 没有 publish / distill / complete 的权威闭环验证

因此它不是死模块，但也还不是主系统已经收口的完成面。

## 运行态现实与工具链漂移

### 1. live 端口现实

本轮实测：

- `127.0.0.1:18711` -> `python`
- `127.0.0.1:18712` -> `python`
- `127.0.0.1:18713` -> `node`

并且：

- `GET http://127.0.0.1:18711/v2/advisor/health` -> `200 OK`
  - `server: uvicorn`
  - `llm.mode: live`
- `GET http://127.0.0.1:18713/v2/advisor/health` -> `404 Not Found`
  - `X-Powered-By: Express`

这说明今天的 live reality 很明确：

- `18711` 是真实 API host
- `18712` 是真实 public MCP host
- `18713` 不是 live advisor host

### 2. 但仓内机器可读治理仍残留 18713 旧事实

这次最需要警惕的不是旧文档，而是“机器可读或半机器可读的治理面仍在撒旧口径”。

证据：

- `AGENTS.md` 仍写 advisor v3 在 18713
  - `AGENTS.md:201`
  - `AGENTS.md:247`
  - `AGENTS.md:255`
- runtime registry 仍把 `advisor_v3` 的 liveness / entry 指向 18713
  - `ops/registries/runtime_registry.yaml:23`
- maint memory 仍写 primary_ports 里 advisor_v3 是 18713
  - `chatgptrest/ops_shared/maint_memory.py:295`
- `scripts/chatgptrest_bootstrap.py --runtime quick` 输出里把 `advisor_v3` 记为 18713 且 `ok: true`
  - 这是因为它吃 runtime registry / quick summary，而不是实际按服务身份复核

这比普通文档冲突更危险，因为它会反向污染：

- maintainer bootstrap
- automated summaries
- downstream tooling assumptions

也就是说，漂移不只存在于 prose docs，已经进入部分工具链现实。

## 本轮测试与核验

### Live checks

- `GET /v2/advisor/health` on `18711`
- `GET /v2/cognitive/health` on `18711`
- `GET /v2/advisor/health` on `18713`
- `ss -ltnp | rg '18711|18712|18713'`
- `WorkspaceService().auth_state()`
- `python scripts/chatgptrest_bootstrap.py --task ... --runtime quick`

### Pytest

本轮点跑通过：

- `tests/test_api_startup_smoke.py`
- `tests/test_routes_agent_v3.py`
- `tests/test_routes_advisor_v3_security.py`
- `tests/test_task_runtime.py`
- `tests/test_workspace_service.py`
- `tests/test_work_memory_manager.py`
- `tests/test_cognitive_api.py`
- `tests/test_context_service_work_memory.py`
- `tests/test_capture_work_memory.py`
- `tests/test_workspace_outbox_handlers.py`
- `tests/test_chatgptrest_bootstrap.py`
- `tests/test_repo_cognition_runtime.py`
- `tests/test_repo_cognition_gitnexus_adapter.py`

## 独立判断

如果只用一句话冻结这次代码优先结论，我会写成：

> ChatgptREST 在代码现实上已经是 execution substrate + advisor graph + public-agent facade + cognitive substrate + governance tooling 的集成宿主；问题不在于它“长成了独立平台”，而在于多个真实子平台已经并存，却没有被明确定义 authority、默认入口、完成权威与退役边界。

更具体地说：

- `jobs_v1` 仍保留低层完成语义权威
- `advisor_v3` 是同步 OpenMind graph 面
- `agent_v3 + public MCP` 是 coding-agent 默认 northbound 面，但 MCP 只是 wrapper，不是新执行引擎
- `cognitive/work_memory` 已经是 OpenMind 主链核心
- `workspace` 是已接线但当前不健康的 side-effect plane
- `repo_cognition` 是真实治理工具层，不是 serving core
- `task_runtime` 是真实 foundation，但还没有成为全仓 authoritative runtime

因此，真正的问题不应再表述成：

> “它本来是 OpenClaw 的插件，后来变独立了，所以乱了。”

而应表述成：

> “它已经在代码里长成多平面宿主，但 authority matrix 没冻结，导致默认入口、完成权威、治理工具层、旁路线和半成品子系统混在一起被讲述。”

## 建议的下一步

### 必须先做

1. 写 repo-level authority matrix
   - `public MCP`
   - `agent_v3`
   - `advisor_v3`
   - `jobs_v1`
   - `cognitive_v2`
   - `task_runtime_v1`
   - `repo_cognition`
   - `workspace`

2. 写 completion authority matrix
   - 谁负责 authoritative `completion_contract`
   - 谁负责 canonical answer
   - 谁负责 work memory writeback
   - 谁只是 provisional projection

3. 清理机器可读治理里的 `18713` 旧事实
   - `AGENTS.md`
   - `ops/registries/runtime_registry.yaml`
   - `chatgptrest/ops_shared/maint_memory.py`
   - `chatgptrest_bootstrap` 的 quick summary 来源

### 之后再做

1. 决定 `task_runtime` 的命运
   - 要么继续孵化并接通 delivery/distillation 权威闭环
   - 要么明确标成 incubating subsystem，禁止在叙事里把它说成主 runtime

2. 决定 `agent_v3` 与 `public MCP` 的关系口径
   - 如果 MCP 是唯一默认入口，就把 `agent_v3` 定义成 governed internal REST facade
   - 如果 `agent_v3` 仍是第一类产品面，就不要再把 direct REST 一律叙述成“非正式路径”

3. 把 `workspace` 的运行态健康纳入正式 gate
   - 现在它在架构上已进入主链，但 token 已过期，不能继续假定它“只是可选工具”
