# 2026-03-20 Authority Matrix v2

## 1. 为什么需要 v2

[2026-03-20_authority_matrix_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_authority_matrix_v1.md) 已经把主运行面、`jobdb`、`artifacts`、`EvoMap knowledge DB`、`OpenClaw -> /v3/agent/turn` 主桥这些事实收出来了，但后续核验指出它还不能直接当最终 freeze 文档。

本版建立在这两份文档之上：

- [2026-03-20_authority_matrix_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_authority_matrix_v1.md)
- [2026-03-20_authority_matrix_verification_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_authority_matrix_verification_v1.md)

v2 的目标不是推翻 v1，而是修正 4 个被压扁的 high-risk row：

1. `front door` 不是两路，而是至少三路
2. `EvoMap` 不是单库，而是 `knowledge DB + signals DB`
3. `ModelRouter` 不能被表述为当前 live advisor runtime 的共治 authority
4. `session truth` 不是两账本，而是至少三账本

## 2. 这版冻结什么

### 2.1 继续冻结的结论

下面这些结论继续成立：

1. `OpenClaw gateway` 是当前唯一持续在线的主 runtime substrate。
2. `~/.openclaw` 是当前 session/channel continuity 的主真相源。
3. `state/jobdb.sqlite3` 是当前 execution/controller/issues/incidents 的主 ledger。
4. `artifacts/` 是 execution 产物主根目录。
5. `data/evomap_knowledge.db` 是 canonical knowledge graph DB。
6. `openclaw_extensions/openmind-advisor -> /v3/agent/turn` 是当前主 OpenClaw live bridge。
7. `cc-sessiond` 仍然只是 residual。

### 2.2 本版新收紧的结论

1. `v2 advisor front door` 不是只有 `/v2/advisor/advise`，还必须显式包含 `/v2/advisor/ask`。
2. `EvoMap runtime state` 至少分成：
   - repo-local `knowledge DB`
   - HOME-relative `signals DB`
3. 当前 live advisor runtime 的模型路由 authority 更准确的描述是：
   - `RoutingFabric + LLMConnector API/static fallback`
   - `ModelRouter` 存在，但未注入当前 runtime composition root
4. 当前 session truth 至少分三层：
   - `~/.openclaw`
   - `state/agent_sessions`
   - `state/jobdb.sqlite3`

## 3. Freeze Rule

仍沿用 v1 的分级：

- `A1 Canonical`
- `A2 Provisional Live`
- `R Residual`
- `U Unresolved`

## 4. 运行时证据快照

### 4.1 当前服务态

截至本次复核：

- `openclaw-gateway.service = active`
- `chatgptrest-api.service = inactive`
- `chatgptrest-mcp.service = inactive`
- `chatgptrest-feishu-ws.service = inactive`

这条不变。

### 4.2 当前 durable 厚度

本次继续沿用已复核过的 live 数据：

- `state/jobdb.sqlite3`
  - `jobs = 7924`
  - `controller_runs = 130`
  - `advisor_runs = 201`
  - `job_events = 1481412`
  - `incidents = 6055`
- `data/evomap_knowledge.db`
  - `documents = 7863`
  - `atoms = 99493`
  - `edges = 90611`
- `/home/yuanhaizhou/.home-codex-official/.openmind/*`
  - `memory_records = 5`
  - `kb_fts_meta = 4`
  - `kb_registry artifacts = 2`
  - `kb_vectors = 0`
  - `events.trace_events = 6`
- `state/agent_sessions`
  - 当前存在 `3` 个 `.json` session 文件和 `3` 个 `.events.jsonl`
- `/tmp/cc-sessions.db`
  - `sessions = 2`

## 5. Authority Matrix v2

| 域 | 当前 authority | 等级 | 证据 | 残留/冲突 | Freeze 结果 | 下一步 |
| --- | --- | --- | --- | --- | --- | --- |
| 常驻 runtime substrate | `openclaw-gateway.service` | `A1 Canonical` | 当前唯一 `active` 服务；gateway 跑在 `18789` | ChatgptREST runtime host 当前停机 | 冻结 | 主链恢复继续从 OpenClaw 出发 |
| Runtime HOME / user state root | `/home/yuanhaizhou/.home-codex-official` | `A1 Canonical` | gateway unit 显式 `Environment=HOME=...` | 其他 shell HOME 可能残留旧状态 | 冻结 | 所有 live-state 核对默认从这一路径看 |
| OpenClaw session/channel continuity | `/home/yuanhaizhou/.home-codex-official/.openclaw` | `A1 Canonical` | gateway 主 session truth；前序盘点已证实持续写入 | backup/reset 快照仍在 | 冻结 | 不再把它降成单纯入口壳 |
| Public agent facade session store | `/vol1/1000/projects/ChatgptREST/state/agent_sessions` | `A2 Provisional Live` | `AgentSessionStore.from_env()` 在有 `CHATGPTREST_DB_PATH` 时落到 `state/agent_sessions`；`routes_agent_v3.py` 已实际实例化并写入；当前目录已有 `3` 套 session/events | 与 OpenClaw session truth 和 jobdb 并存 | 明确纳入 session truth 问题，而不是漏掉 | 后续专门做 `session_truth_decision_v1` |
| ChatgptREST execution/controller ledger | `/vol1/1000/projects/ChatgptREST/state/jobdb.sqlite3` | `A1 Canonical` | drop-in 显式覆盖 DB 路径；live 厚度最高 | 基础 unit 仍残留旧 worktree 路径 | 冻结 | 继续作为 execution/controller/issues 主账本 |
| ChatgptREST artifacts | `/vol1/1000/projects/ChatgptREST/artifacts` | `A1 Canonical` | API/MCP drop-in 都覆盖到 repo-local artifacts | 旧 worktree 和 `/tmp` 有历史证据包 | 冻结 | 继续与 jobdb 配套使用 |
| EvoMap knowledge DB | `/vol1/1000/projects/ChatgptREST/data/evomap_knowledge.db` | `A1 Canonical` | `resolve_evomap_knowledge_runtime_db_path()` 默认回 repo-local；live 厚度最高；consult/read path 也偏向这里 | 不应再被压缩成“整个 EvoMap runtime 的唯一 DB” | 冻结为 canonical knowledge graph DB | 后续知识决策以它为主库 |
| EvoMap signals / observer DB | `/home/yuanhaizhou/.home-codex-official/.openmind/evomap/signals.db` | `A2 Provisional Live` | `resolve_evomap_db_path()` 默认 `~/.openmind/evomap/signals.db`；`advisor/runtime.py` 用它初始化 `EvoMapObserver`、team scorecard、team policy、team control plane | 容易被遗漏，从而误判 EvoMap 为单库 | 明确单列，不再隐含吞并到 knowledge DB 行 | 后续知识与 telemetry 决策要区分 knowledge plane vs signals plane |
| OpenMind memory DB | `/home/yuanhaizhou/.home-codex-official/.openmind/memory.db` | `A2 Provisional Live` | `MemoryManager` 默认 HOME-relative；当前 live 库确实在这里 | 数据很薄；不能误写成 canonical knowledge store | 暂认定为 runtime memory | 见 `knowledge_authority_decision_v2` |
| OpenMind KB search DB | `/home/yuanhaizhou/.home-codex-official/.openmind/kb_search.db` | `A2 Provisional Live` | `KBHub` 默认走 HOME-relative search db；当前库存在 | 仍与 canonical knowledge plane 不同 | 暂认定为 KB working set | 见 `knowledge_authority_decision_v2` |
| OpenMind KB registry/vector DB | `/home/yuanhaizhou/.home-codex-official/.openmind/kb_registry.db` / `kb_vectors.db` | `A2 Provisional Live` | `ArtifactRegistry`/`KBHub` 默认走 HOME-relative；当前 live registry 很薄 | 不能继续被表述成厚知识中心 | 暂认定为 artifact/evidence working set | 见 `knowledge_authority_decision_v2` |
| OpenMind event bus DB | `/home/yuanhaizhou/.home-codex-official/.openmind/events.db` | `A2 Provisional Live` | `EventBus` 默认 HOME-relative；runtime 初始化实际使用 | 目前厚度很薄，不能当 system ledger | 暂认定为 runtime event backbone | 见 `knowledge_authority_decision_v2` |
| Public live ask ingress | `/v3/agent/turn` | `A1 Canonical` | OpenClaw 当前主桥直连它；coding-agent surface policy 也要求优先走 public agent surface | 与 v2 advisor ingress 并存 | 冻结为当前 public/live ask 正门 | 后续 front-door contract 以它为主 anchor |
| Advisor graph ingress | `/v2/advisor/advise` | `A2 Provisional Live` | `routes_advisor_v3.py` 完整 advisor graph 入口；Feishu WS service 仍默认指向它 | 与 `/v3/agent/turn` 和 `/v2/advisor/ask` 并存 | 明确保留，但不再写成 v2 的唯一 front door | 在 `front_door_contract_v1` 明确边界 |
| Unified advisor ask ingress | `/v2/advisor/ask` | `A2 Provisional Live` | `routes_advisor_v3.py` 明确实现；`chatgptrest_advisor_ask` MCP 工具实际 POST 到这里 | v1 matrix 漏掉了它；与 `/advise` 和 `/turn` 语义重叠 | 新增这一行，明确 front door 至少三路 | 在 `front_door_contract_v1` 决定它未来地位 |
| OpenClaw main bridge | `openclaw_extensions/openmind-advisor` | `A1 Canonical` | 插件默认 `baseUrl=18711`，直连 `/v3/agent/turn`，透传 session/account/thread/agent identity | 历史 `openclaw_adapter.py` 仍存在 | 冻结为当前主 OpenClaw bridge | 旧桥降级为 compat |
| Feishu ingress target | `chatgptrest-feishu-ws.service -> /v2/advisor/advise` | `U Unresolved` | systemd unit 与默认代码都指向 `/v2/advisor/advise` | 与 OpenClaw 主桥 `/v3/agent/turn` 不一致；还绕开 `/v2/advisor/ask` | 暂不冻结 | front-door contract 必须处理 |
| Routing policy contract | `RoutingFabric` | `U Unresolved` | `routing/fabric.py` 自述为 unified entry point；runtime 实际会初始化并 attach 它 | contract 与 actual invoke 仍未完全一致 | 继续作为设计 authority 候选，但不写成 fully converged | 进入 `routing_authority_decision_v1` |
| Current live API invocation chain | `RoutingFabric + LLMConnector static/API fallback` | `A2 Provisional Live` | 当前 advisor runtime 构造 `LLMConnector` 时未注入 `ModelRouter`；只 attach 了 `RoutingFabric`；`LLMConnector._select_model()` 走 `RoutingFabric -> static route map -> provider fallbacks`，若 future 注入 `model_router` 才会用 | `ModelRouter` 和 `routing_engine` 存在，但未进入当前 live composition root | 修正 v1 的过强表述 | 在 routing 决策文档里明确 dormant vs live |
| ModelRouter | code exists but not wired into current advisor runtime | `R Residual` | grep 只看到定义和可选 constructor slot；当前 runtime 没有注入它 | 容易被误读为 live co-authority | 降级为 dormant path / future option | 后续要么真正接入，要么继续降级 |
| Session truth | `~/.openclaw` + `state/agent_sessions` + `state/jobdb.sqlite3` | `U Unresolved` | 三套 ledger 都在实际使用 | v1 只写成两账本，低估了 split-brain | 修正为至少三账本 | 后续必须单独做 session truth 决策 |
| Telemetry ingest endpoint | `POST /v2/telemetry/ingest` | `A2 Provisional Live` | 路由真实挂载存在；ops smoke/closeout 也按此路径写 | gateway 持续刷 `fetch failed`；runtime host 当前停机；closeout 仍见 `18713` 返回 404 | 路径仍明确，但 runtime 健康性未解决 | 进入 `telemetry_contract_fix_v1` |
| cc-sessiond / team runtime | `/tmp/cc-sessions.db` + `/tmp/artifacts/cc_sessions` | `R Residual` | 当前仅 `2` 条 session；不是主链中心 | 仍容易被误判成 team execution 主 authority | 保持降级 | 只留作实验/历史残留 |
| systemd worktree base-unit paths | base unit 旧 worktree，drop-in repo-local override 才是真 authority | `R Residual` | 当前有效路径来自 drop-ins，不是 base unit 注释与默认值 | 持续制造认知噪音 | 继续降级 base unit 旧路径 | 后续清理 systemd unit 文件 |

## 6. Freeze Decisions v2

### 6.1 现在就冻结

下面这些现在可以继续作为明确事实源：

- `OpenClaw gateway`
- `~/.openclaw`
- `state/jobdb.sqlite3`
- `artifacts/`
- `data/evomap_knowledge.db`
- `openclaw_extensions/openmind-advisor -> /v3/agent/turn`

### 6.2 现在明确拆分，而不是压扁

下面这些以后不能再被单行压扁描述：

- `front door`
  - `/v3/agent/turn`
  - `/v2/advisor/advise`
  - `/v2/advisor/ask`
- `EvoMap`
  - `knowledge DB`
  - `signals DB`
- `session truth`
  - `~/.openclaw`
  - `state/agent_sessions`
  - `state/jobdb.sqlite3`

### 6.3 现在明确降级

- `ModelRouter`
  - 当前 advisor runtime 未接入，不能继续被写成 live 共治 authority
- `cc-sessiond`
- 旧 `openclaw_adapter.py`
- systemd base unit 里的旧 worktree 路径

## 7. 与 v1 的关键差异

相比 v1，这版最重要的修正是：

1. 不再把 `v2 advisor` 压缩成只有 `/advise`
2. 不再把 `EvoMap` 压缩成只有 knowledge DB
3. 不再把 `ModelRouter` 写成当前 live runtime 的共治权威
4. 不再把 session truth 写成两账本

## 8. 下一步

基于 v2，`Phase 0` 后续顺序应该是：

1. `knowledge_authority_decision_v2`
   - 纳入 `EvoMap signals DB`
2. `routing_authority_decision_v1`
   - 明确 `RoutingFabric` 和 `LLMConnector` 的当前主从关系
3. `front_door_contract_v1`
   - 明确三路入口分工
4. `session_truth_decision_v1`
   - 单独处理三账本收敛
5. `telemetry_contract_fix_v1`
   - 解决 runtime target 不健康问题

## 9. 最小结论

`authority_matrix_v1` 的主方向是对的，但不能直接拿来做最终 freeze。

从 v2 开始，应该按下面这个更真实的结构理解系统：

- `OpenClaw` 是 live runtime substrate
- `ChatgptREST jobdb` 是 execution ledger
- `EvoMap` 至少是双库：
  - repo-local knowledge DB
  - HOME-relative signals DB
- `front door` 至少是三路：
  - `/v3/agent/turn`
  - `/v2/advisor/advise`
  - `/v2/advisor/ask`
- `session truth` 至少是三账本

只有按这个粒度继续规划，后面的 Phase 0 决策才不会再次建立在压扁叙事上。
