# 2026-03-20 Authority Matrix v1

## 1. 目的

这份文档是 [2026-03-20_post_reconciliation_next_phase_plan_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_post_reconciliation_next_phase_plan_v1.md) 里 `Phase 0: Authority Freeze` 的第一份交付物。

它只做一件事：

- 把当前系统里哪些对象已经可以冻结为 `single source of truth`
- 哪些对象只是 `live runtime residue`
- 哪些对象仍然处在 `split-brain / unresolved authority`

写清楚。

这里的 authority 不等于“理想架构”，而是 **2026-03-20 当前代码、systemd、数据库和活跃服务共同指向的实际事实源**。

## 2. 执行摘要

当前可以先冻结的结论有 7 条：

1. `OpenClaw gateway` 是当前唯一持续在线的主运行底座。
2. `~/.openclaw` 是 session/channel continuity 的真实台账。
3. `state/jobdb.sqlite3` 是当前最厚、最可靠的 execution/controller/issues ledger。
4. `artifacts/` 是当前与 `jobdb` 配套的主产物目录。
5. `data/evomap_knowledge.db` 是 EvoMap runtime graph 的 canonical DB。
6. `openclaw_extensions/openmind-advisor -> /v3/agent/turn` 是当前 live ask/public bridge 的正门。
7. `cc-sessiond / team runtime` 只能算实验资产和残留执行面，当前不能被视为主 authority。

当前不能直接冻结、必须继续做 Phase 0 决策的有 4 条：

1. `OpenMind memory / KB / event bus` 的 canonical path 仍未定死。
2. 模型路由 authority 仍然是 `RoutingFabric + ModelRouter + LLMConnector static fallback` 并存。
3. `Feishu ingress` 仍然默认指向 `/v2/advisor/advise`，和当前 live ask 正门不一致。
4. telemetry 合同在路径层面基本明确，但运行层面仍是 broken 状态。

补一个会持续影响判断的细节：

- 当前 `/home/yuanhaizhou/.config/chatgptrest/chatgptrest.env` 只显式提供了 `OPENMIND_API_KEY`、`OPENMIND_AUTH_MODE`、`OPENMIND_RATE_LIMIT`
- **没有** 显式固定 `OPENMIND_MEMORY_DB`、`OPENMIND_KB_SEARCH_DB`、`OPENMIND_KB_VEC_DB`、`OPENMIND_EVENTBUS_DB`、`EVOMAP_KNOWLEDGE_DB`

因此今天 `memory / KB / event bus` 的 authority 实际上不是被 env 显式锁死，而是被 `gateway HOME` 间接决定。

## 3. Freeze Rule

从本文件起，authority 先按 4 个等级说话：

- `A1 Canonical`
  - 当前必须被当作唯一事实源
- `A2 Provisional Live`
  - 当前运行时在用，但不代表长期 canonical
- `R Residual`
  - 历史残留、旁路、只读兼容或实验资产
- `U Unresolved`
  - 当前仍存在并行真相源，不能假装已统一

## 4. 运行时证据快照

### 4.1 当前服务态

截至本次核对：

- `openclaw-gateway.service = active`
- `chatgptrest-api.service = inactive`
- `chatgptrest-mcp.service = inactive`
- `chatgptrest-feishu-ws.service = inactive`

这意味着：

- 当前唯一 live runtime substrate 是 `OpenClaw`
- `ChatgptREST` 仍然是最厚的 durable host，但它此刻并未运行

### 4.2 当前 durable 厚度

本次直接核对到的关键数据库量级：

- `state/jobdb.sqlite3`
  - `jobs = 7924`
  - `controller_runs = 130`
  - `advisor_runs = 201`
- `data/evomap_knowledge.db`
  - `documents = 7863`
  - `atoms = 99493`
  - `edges = 90611`
- `/home/yuanhaizhou/.home-codex-official/.openmind/*`
  - `memory_records = 5`
  - `kb_fts_meta = 4`
  - `kb_registry artifacts = 2`
  - `kb_vectors = 0`
- `/tmp/cc-sessions.db`
  - `sessions = 2`

这组数字支持两个关键判断：

1. `jobdb + repo-local EvoMap` 是厚 authority。
2. 当前 live `OpenMind memory/KB` 仍然是薄 authority，只能先视为 `A2 Provisional Live`。

## 5. Authority Matrix

| 域 | 当前 authority | 等级 | 证据 | 残留/冲突 | Freeze 结果 | 下一步 |
| --- | --- | --- | --- | --- | --- | --- |
| 常驻 runtime substrate | `openclaw-gateway.service` | `A1 Canonical` | 当前唯一 `active` 服务；gateway 运行于 `18789` | ChatgptREST runtime host 当前停机 | 冻结为当前主运行底座 | 后续所有主链恢复都从 OpenClaw 出发 |
| Runtime HOME / user state root | `/home/yuanhaizhou/.home-codex-official` | `A1 Canonical` | `openclaw-gateway.service` 显式 `Environment=HOME=/home/yuanhaizhou/.home-codex-official` | 其他 shell/用户 HOME 可能存在旧状态 | 冻结为当前 live HOME | 之后所有 OpenClaw/OpenMind live-state 核对默认从这一路径看 |
| OpenClaw session/channel continuity | `/home/yuanhaizhou/.home-codex-official/.openclaw` | `A1 Canonical` | gateway session truth 长期落此目录；前序审计已证实 `main / maintagent / finbot` 持续写入 | 历史 migration backup 和 reset backup 仍保留 | 冻结为 session truth | 不再把 ChatgptREST facade session 当唯一真相源 |
| ChatgptREST execution ledger | `/vol1/1000/projects/ChatgptREST/state/jobdb.sqlite3` | `A1 Canonical` | `chatgptrest-api.service` drop-in 显式覆盖 DB 路径；`jobs=7924`、`controller_runs=130`、`advisor_runs=201` | 历史 worktree unit 仍残留相对路径写法 | 冻结为 execution/controller/issues 主账本 | 删除 systemd base unit 里的陈旧 worktree 路径描述 |
| ChatgptREST artifacts | `/vol1/1000/projects/ChatgptREST/artifacts` | `A1 Canonical` | `chatgptrest-api.service` / `chatgptrest-mcp.service` drop-in 均覆盖到 repo-local `artifacts` | 历史工作树或 `/tmp` 里有旧证据包 | 冻结为 repo 当前主产物根目录 | 跟 jobdb 一起作为 execution audit root |
| EvoMap runtime graph DB | `/vol1/1000/projects/ChatgptREST/data/evomap_knowledge.db` | `A1 Canonical` | `openmind_paths.resolve_evomap_knowledge_runtime_db_path()` 默认回 repo-local canonical；实库厚度最高 | `~/.openmind/evomap_knowledge.db` 是 legacy scratch residue | 冻结为 EvoMap canonical DB | 下一个知识 authority 决策文档继续明确 import / review / archive 关系 |
| OpenMind memory DB | `/home/yuanhaizhou/.home-codex-official/.openmind/memory.db` | `A2 Provisional Live` | `openmind_paths` 默认 HOME-relative；gateway HOME 已锁定；当前 live 数据确实落在此处 | 数据很薄，不足以支撑“厚知识 authority”判断 | 暂认定为当前 live memory store，不升格为长期 canonical | 在 `knowledge_authority_decision_v1` 里决定是否显式 env 固定或并表/降级 |
| OpenMind KB search DB | `/home/yuanhaizhou/.home-codex-official/.openmind/kb_search.db` | `A2 Provisional Live` | `resolve_openmind_kb_search_db_path()` 默认 `~/.openmind/kb_search.db`；当前 live 库存在 | 仍可能与 repo 侧其他 KB residue 混淆；数据很薄 | 暂认定为 live KB front-door store | 需要和 KB registry/vector 一起做 authority 决策 |
| OpenMind KB registry/vector DB | `/home/yuanhaizhou/.home-codex-official/.openmind/kb_registry.db` / `kb_vectors.db` | `A2 Provisional Live` | 当前 live 文件存在；registry 仅 `2` 条 artifact，vectors 为 `0` | 与“KB 很厚”的历史印象冲突明显 | 暂不升格为厚 authority | 明确它是前门轻层、还是需要迁回 repo canonical |
| OpenMind event bus DB | `/home/yuanhaizhou/.home-codex-official/.openmind/events.db` | `A2 Provisional Live` | `resolve_openmind_event_bus_db_path()` 默认 HOME-relative；gateway HOME 已锁定 | 目前缺少与 repo execution ledger 的清晰 authority 分工 | 暂认定为 OpenMind local event/log store | 需要在知识/telemetry authority 决策里一起收口 |
| Public live ask ingress | `/v3/agent/turn` | `A1 Canonical` | `routes_agent_v3.py` 自带 session-first facade；OpenClaw `openmind-advisor` 插件直接打此入口；`coding_agent_mcp_surface_policy` 也明确要求 coding agent 走 public agent surface | `/v2/advisor/advise`、旧 MCP 裸工具、legacy v1 advisor 仍存在 | 冻结为 live ask/public bridge 正门 | 之后统一外部入口优先级时，把 `/v3/agent/turn` 放在第一位 |
| Advisor graph ingress | `/v2/advisor/advise` | `A2 Provisional Live` | `routes_advisor_v3.py` 仍是完整 advisor/langgraph 入口；Feishu WS service 默认仍指向它 | 与 `/v3/agent/turn` 入口语义重叠；容易造成 front-door split | 继续保留为 advisor graph / legacy slow-path 入口，不视为唯一正门 | 在 `front_door_contract_v1` 明确它的角色边界 |
| OpenClaw main bridge | `openclaw_extensions/openmind-advisor` | `A1 Canonical` | 插件默认 `baseUrl=http://127.0.0.1:18711`，直连 `/v3/agent/turn`，透传 `session_id/account_id/thread_id/agent_id` | 历史 `openclaw_adapter.py` 仍是并行桥 | 冻结为当前主桥 | 把 `openclaw_adapter.py` 降成 residue/compat 层 |
| Feishu ingress target | `chatgptrest-feishu-ws.service -> ADVISOR_API_URL=http://127.0.0.1:18711/v2/advisor/advise` | `U Unresolved` | systemd 单元当前写死此入口；`feishu_ws_gateway.py` 默认也指向同一路径 | 与 `OpenClaw -> /v3/agent/turn` 的当前主桥不一致 | 暂不冻结 | 必须在 `front_door_contract_v1` 决定 Feishu 是否改走 `/v3/agent/turn` |
| Model routing contract | `RoutingFabric` 是设计主 authority，但未闭环 | `U Unresolved` | `routing/fabric.py` 自述是 unified entry point；`advisor/runtime.py` 注入 fabric | `ModelRouter`、`routing_engine`、`LLMConnector._select_model()` 仍共同参与 | 不能宣称已统一 | 在 `routing_authority_decision_v1` 收敛为一套 contract |
| Actual API model invocation chain | `LLMConnector._select_model()` | `A2 Provisional Live` | 实际 API-only 调用链仍是 `RoutingFabric -> ModelRouter -> static route map -> Gemini/MiniMax fallback` | “选路一套、执行一套”的 split 仍存在 | 暂认定为当前真实执行链 | 后续要么让 `RoutingFabric` 真正 provider-aware invoke，要么降级它为纯 policy |
| Session-first facade state | `OpenClaw session + ChatgptREST job/controller ledger` 的组合 | `U Unresolved` | OpenClaw持有 channel continuity；`routes_agent_v3.py` 也有 own session store | 存在 facade session 与底层 execution 双账本 | 暂不把单一 facade store 升格为 authority | 下一步需要 `session truth` 专项收敛说明 |
| Telemetry ingest endpoint | `POST /v2/telemetry/ingest` | `A2 Provisional Live` | `routes_cognitive.py` 真实挂载该路径；ops smoke/closeout 也按此路径写 | gateway 当前持续刷 `openmind-telemetry: flush failed: TypeError: fetch failed`；runtime host 当前停机 | 路径基本明确，但 runtime 不健康，不能算 `A1` | 下一步先修 target + live service，再做 `telemetry_contract_fix_v1` |
| cc-sessiond / team runtime | `/tmp/cc-sessions.db` + `/tmp/artifacts/cc_sessions` | `R Residual` | 当前 DB 仅 `2` 条 session；已不再是主链中心 | 容易被误判成 execution authority | 明确降级为实验/历史残留 | 只保留可回收契约，不再当主系统中心 |
| systemd worktree path authority | repo-local drop-ins 胜出，base unit 仍残留旧 worktree | `R Residual` | `chatgptrest-api.service` / `mcp.service` drop-in 已覆盖 WorkingDirectory/PYTHONPATH/DB/artifacts | base unit 仍保留 `chatgptrest-advisor-agent-facade-20260317` 路径，制造认知噪音 | 认定 drop-in 才是当前 authority | 后续做一次 unit 文件清洁，移除误导性老路径 |

## 6. Freeze Decisions

### 6.1 现在就冻结

下面这些项从现在开始应被当作明确事实源：

- `OpenClaw gateway` 是 live runtime substrate
- `~/.openclaw` 是 session/channel continuity truth
- `state/jobdb.sqlite3` 是 execution/controller/issues 主账本
- `artifacts/` 是主产物根目录
- `data/evomap_knowledge.db` 是 EvoMap canonical DB
- `openclaw_extensions/openmind-advisor -> /v3/agent/turn` 是当前 live/public ask 正门

### 6.2 现在明确降级

下面这些项从现在开始只能当作残留或旁路：

- `cc-sessiond`
- `team child executor` 旧式中心化想象
- 历史 worktree unit 路径
- 旧 `openclaw_adapter.py` 主桥定位

### 6.3 现在禁止假装已统一

下面这些项当前仍然不能宣称“已经统一完成”：

- `OpenMind memory / KB / event bus` authority
- 模型路由 authority
- Feishu front door authority
- telemetry authority
- facade session truth

## 7. Immediate Action List

按优先级，`Phase 0` 后续动作应该是：

1. 写 `knowledge_authority_decision_v1`
   - 明确 `memory / KB / event bus` 是继续 HOME-relative live store，还是转成 repo-local canonical state
2. 写 `routing_authority_decision_v1`
   - 明确 `RoutingFabric`、`ModelRouter`、`routing_engine`、`LLMConnector` 的主从关系
3. 写 `front_door_contract_v1`
   - 明确 `/v3/agent/turn`、`/v2/advisor/advise`、Feishu ingress 的角色边界
4. 写 `telemetry_contract_fix_v1`
   - 修 gateway telemetry flush 的 target/availability
   - 修 closeout mirror 的 live 404 现象
5. 清理 systemd 陈旧 worktree 路径
   - 不是为了功能，而是为了停止继续制造错误心智模型

## 8. 最小结论

当前系统已经有一条足够明确的主骨架：

- `OpenClaw` 持有在线 runtime 和 session continuity
- `ChatgptREST` 持有 execution/controller ledger
- `EvoMap` 持有最厚的 repo-local knowledge graph
- `OpenMind` 的前门方法论已经部分落在 `ChatgptREST advisor` 里

真正还没冻结的，不是“系统有没有做”，而是：

- `front door`
- `memory/KB authority`
- `model routing`
- `telemetry`

下一步不该再继续长新模块，而是把这四件事收口。
