# 2026-03-20 System State Reconciliation Master Audit v2

## 1. 为什么需要 v2

[2026-03-20_system_state_reconciliation_master_audit_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_system_state_reconciliation_master_audit_v1.md) 已经把 `2026-03-18` 到 `2026-03-20` 的主状态对齐了一次，但用户要求继续往前追溯几天。

这次 v2 的目的不是简单把 timeline 拉长，而是补上 `2026-03-07` 到 `2026-03-17` 这段真正塑造今天系统状态的演化链，回答两个更深的问题：

1. 今天这些边界冲突和口径混乱是怎么逐步形成的。
2. 哪些模块虽然今天看上去“很乱”，但其实已经有连续演化主线，不能被误判成死代码或偶然拼装。

## 2. v2 相比 v1 的增量

本版新增：

- 追溯窗口从 `2026-03-18` 向前扩展到 `2026-03-07`
- 补充 `advisor runtime / RoutingFabric / OpenClaw rebuild / memory vertical slice / EvoMap authority / team control plane / controller unification / system optimization / public agent facade` 的历史节点
- 对“为什么今天会出现 memory/KB 与 EvoMap 不对称、OpenClaw 与 ChatgptREST 重叠、cc-sessiond 中心性被误判”给出时间线解释

本版仍然保留 v1 的核心勘误结论：

- `OpenClaw` 被低估了
- `EvoMap` 被低估了
- 当前运行态 `OpenMind memory/KB` 被高估了
- `cc-sessiond/team runtime` 的中心性被高估了
- `public agent / premium ingress strategist` 的完成度被低估了

## 3. 当前可作为计划输入的稳定事实

先把今天这个时点的稳定事实再压一遍，避免时间线把焦点冲散。

### 3.1 当前服务状态

本次核实到：

- `openclaw-gateway.service = active/running`
- `chatgptrest-api / dashboard / driver / feishu-ws / maint-daemon / mcp / worker-*` 当前全部 `inactive/dead`

也就是说：

- **OpenClaw runtime 还活着**
- **ChatgptREST runtime lane 现在是静态停机**

### 3.2 当前 durable 数据厚度

当前最厚的 durable 状态资产仍是：

- `state/jobdb.sqlite3`
- `data/evomap_knowledge.db`

其中：

- `jobdb` 仍然是最成熟的 execution/controller/issues/incidents ledger
- `EvoMap` 仍然是最厚的知识资产

### 3.3 当前 OpenMind memory/KB live 事实

当前 `HOME=/home/yuanhaizhou/.home-codex-official` 运行面的 OpenMind 数据库实测仍然很小：

- `memory_records = 5`
- `kb_fts_meta = 4`
- `kb_registry artifacts = 2`
- `kb_vectors = 0`

因此，下一步规划不能再用“memory/KB 已经和 EvoMap 一样成熟”这个前提。

## 4. 2026-03-07 到 2026-03-20 的关键演化时间线

这一节只保留真正改变今天状态的节点，不做逐日流水账。

### 4.1 2026-03-07：runtime composition root 和单一路由栈开始成型

关键文档：

- [2026-03-07_systemic_audit_83_90_refactor.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-07_systemic_audit_83_90_refactor.md)

这个节点的历史意义很大：

- `advisor/runtime.py` 被正式抽出来，成为 Advisor composition root
- `routes_advisor_v3.py::_init_once()` 开始收敛为 runtime lookup，而不是在 route 里临时重建整套 advisor stack
- `RoutingFabric` 在当时被明确推进为主路由栈
- `LLMConnector` 开始接受 injected `RoutingFabric`，而不是反向拉 ambient globals
- control-plane helpers 和 repair request shaping 也开始脱离 worker/MCP/ops 各自为政

结论：

- 到 `03-07` 为止，今天这套 `AdvisorRuntime / RoutingFabric / shared control-plane` 骨架已经不是临时拼法，而是有明确收敛方向的
- 这也是为什么今天不能简单把 `ChatgptREST advisor` 说成“路由散装拼出来的”

### 4.2 2026-03-08：OpenClaw 与 OpenMind 的 integrated-host 现实被钉死

关键文档：

- [2026-03-08_openclaw_openmind_rebuild_round2.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-08_openclaw_openmind_rebuild_round2.md)
- [2026-03-08_feishu_history_routing_fix.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-08_feishu_history_routing_fix.md)

这一轮真正定下来的不是“装了几个插件”，而是运行事实：

- OpenMind bridge 当时按 integrated host reality 指向 `http://127.0.0.1:18711`
- OpenClaw plugin 安装流被收敛到官方 CLI `openclaw plugins install --link`
- OpenClaw/Feishu 与 OpenMind advisor 已经进入真实业务消息验证
- `graph.py:analyze_intent()` 的意图判别已经开始被真实 Feishu 历史消息回打

结论：

- 到 `03-08`，OpenClaw 已经不是未来构想，而是现实里的 shell/runtime substrate
- Feishu 路由和 advisor intent 也已经进入 live-like 业务风格验证阶段

### 4.3 2026-03-09：OpenClaw shell / OpenMind cognition 的产品边界第一次被明确做实

关键文档：

- [2026-03-09_openclaw_openmind_best_practice_rebuild.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-09_openclaw_openmind_best_practice_rebuild.md)
- [2026-03-09_openmind_memory_capture_vertical_slice.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-09_openmind_memory_capture_vertical_slice.md)
- [2026-03-09_openmind_memory_recall_budget_fix.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-09_openmind_memory_recall_budget_fix.md)

`03-09` 的意义不在某一个 patch，而在三个决定：

1. **OpenClaw topology 被大幅简化**
   - 从多持久 lane 设想，收敛到 `lean` 和 `ops`
   - `main` 成为真正工作台
   - `maintagent` 降成可选 watchdog

2. **OpenMind memory 走出第一个真实 vertical slice**
   - `openmind-memory` plugin
   - `/v2/memory/capture`
   - episodic memory + audit trail
   - `/v2/context/resolve` 回灌 `Remembered Guidance`

3. **OpenClaw gateway 与 ChatgptREST env authority 被绑定**
   - `openclaw-gateway.service` 加载 `~/.config/chatgptrest/chatgptrest.env`
   - 目的是让 OpenMind telemetry auth 与 integrated host 共用同一套 authority

结论：

- 这一天实际上确立了今天仍然成立的产品分层直觉：
  - `OpenClaw = shell/runtime`
  - `OpenMind = cognition substrate`
- 但也埋下了今天的一个隐患：
  - OpenClaw gateway 开始吃 ChatgptREST/OpenMind env
  - 系统边界变实了，但 authority 也开始纠缠了

### 4.4 2026-03-10：dual-DB / resolver / authority 问题第一次被系统性说透

关键文档：

- [2026-03-10_authoritative_db_import_analysis_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-10_authoritative_db_import_analysis_v1.md)
- [2026-03-10_evomap_current_vs_openclaw_gap_analysis_v2.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-10_evomap_current_vs_openclaw_gap_analysis_v2.md)
- [2026-03-10_shared_resolver_and_memory_identity_hardening.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-10_shared_resolver_and_memory_identity_hardening.md)
- [2026-03-10_codex_cutover_plan_verification_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-10_codex_cutover_plan_verification_v1.md)
- [2026-03-10_feishu_ws_gateway_auth_ingress_fix.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-10_feishu_ws_gateway_auth_ingress_fix.md)
- [2026-03-10_feishu_ws_service_env_fix.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-10_feishu_ws_service_env_fix.md)

这一天是今天很多混乱的源头说明书。

#### 4.4.1 EvoMap dual-DB divergence 被明确指出

当时已经明确：

- runtime canonical DB 是 `data/evomap_knowledge.db`
- `~/.openmind/evomap_knowledge.db` 是旧 scratch / ops DB
- 两套库数据完全不同，不能混用

这直接解释了为什么今天任何“知识层盘点”都必须先问：

- 你查的是哪一套 DB
- 它是 runtime authority 还是 scratch/ops residue

#### 4.4.2 shared resolver / memory identity hardening 落地

`03-10` 还做了更底层的事情：

- runtime 与 consult 开始共享 `openmind_paths`
- ignore zero-byte HOME EvoMap fallback
- extractor 默认关掉，避免隐式 graph growth
- memory recall/capture 的 identity 和 provenance 质量开始被当作 hot-path diagnostics 问题

这和今天的对账结论高度相关：

- 路径与 authority 问题，不是今天才出现
- 从 `03-10` 就已经是主矛盾之一

#### 4.4.3 Feishu WS auth / ingress contract 仍在摇摆

`03-10` 的两份 Feishu 文档说明：

- WS gateway 入口到底该打 `18711` 还是 `18713`，当时就不是稳定事实
- `OPENMIND_API_KEY` 是否在 Feishu WS runtime 可见，也要靠 systemd env 对齐

这也解释了为什么后面 OpenClaw / ChatgptREST / Advisor 的入口层一直容易出现“哪个端口才是正门”的认知噪音

### 4.5 2026-03-11：observe-first 运行守护与 EvoMap runtime gate 同时出现

关键文档：

- [2026-03-11_openclaw_runtime_guard_v0_1_v1.md](/vol1/1000/projects/ChatgptREST/docs/ops/2026-03-11_openclaw_runtime_guard_v0_1_v1.md)
- [2026-03-11_evomap_db_lock_hardening.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-11_evomap_db_lock_hardening.md)
- [2026-03-11_evomap_recall_activation_smoke.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-11_evomap_recall_activation_smoke.md)
- [2026-03-11_planning_evomap_execution_report_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-11_planning_evomap_execution_report_v1.md)

这一天的关键不是“又加了几个 smoke”，而是两个方向：

1. **OpenClaw runtime guard**
   - 明确是 observe-first sidecar
   - 不改 controller，不改 policy，不改 retrieval defaults
   - 先把 detector contract 固化

2. **planning / EvoMap**
   - 多份文档都明确强调：
     - 当前是 review-plane / archive-plane 语义
     - 不是默认 runtime retrieval cutover

结论：

- 到 `03-11`，团队已经非常清楚“runtime cutover”和“review/archive plane”不是一回事
- 这条边界后面被忘掉了很多次，但它其实早就写得很清楚

### 4.6 2026-03-12：advisor path convergence 开始把 OpenClaw 插件和 Advisor ingress 收口

关键文档：

- [2026-03-12_advisor_path_convergence_walkthrough_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-12_advisor_path_convergence_walkthrough_v1.md)

这一轮的核心是：

- `/v2/advisor/advise` 和 `/v2/advisor/ask` 开始共享 request metadata 回传
- health 中显式暴露 `degraded` 状态
- OpenClaw `openmind-advisor` 插件从 sync-like 使用方式改成更适合长任务的 async-first 契约
- Feishu WS 入口开始透传 trace/context

结论：

- 到 `03-12`，OpenClaw plugin 和 Advisor ingress 已经在做契约收敛
- 这说明后来出现的 `public agent facade` 不是凭空冒出来的一层，而是沿着这条入口契约收敛线继续走出来的

### 4.7 2026-03-13：runtime knowledge policy 与 memory hotpath 开始联动

关键证据：

- `325b57c` `fix: make openclaw memory recall knowledge aware`
- [2026-03-13_* convergence / runtime knowledge policy 相关提交与文档](/vol1/1000/projects/ChatgptREST/docs/dev_log)

`03-13` 的重点不是某一份单独蓝图，而是：

- runtime knowledge policy surfaces 开始显式化
- live validation / convergence / startup manifest 开始系统化
- OpenClaw memory recall 不再只看 capture，还开始变成 knowledge-aware hotpath

结论：

- 这一天之后，“记忆 / 知识 / runtime hotpath” 三者已经不是孤立 patch
- 但今天看运行态时，memory/KB live 数据很薄，说明这条线后面没有在当前 HOME/runtime 下继续做厚

### 4.8 2026-03-14：team control plane runtime 正式长出来

关键文档：

- [2026-03-14_team_control_plane_clean_execution_plan_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-14_team_control_plane_clean_execution_plan_v1.md)
- [2026-03-14_team_control_plane_clean_walkthrough_v3.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-14_team_control_plane_clean_walkthrough_v3.md)

这一轮说明两件事：

1. `team_control_plane` 不是空名词
   - checkpoint 终态语义
   - topology overlay
   - `max_concurrent`
   - advisor runtime integration
   - team-control routes

2. 它当时是认真做过 clean implementation 和 full-suite validation 的

结论：

- 今天不能把 `team control plane` 说成纯概念
- 但它也没有成为后续主运行中心
- 更准确的判断是：**这是重执行/多角色协作方向的一块真实实验资产**

### 4.9 2026-03-15：controller ledger 从 ask 语义推进到 objective/run/step 语义

关键文档：

- [2026-03-15_openmind_controller_unification_walkthrough_v2.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-15_openmind_controller_unification_walkthrough_v2.md)

这一天对今天影响非常大。

真正落地的是：

- `controller_runs` 开始持久化 objective-first 字段
- `action` 和 `team` 不再只是 route 内的小分支，而是进入 controller 主回路
- `get_run_snapshot()` 开始做 job/team state reconciliation
- team child executor 正式接进 controller 主链

结论：

- 从 `03-15` 开始，今天我们看到的 controller 不是“为了 dashboard 凑个表”
- 它已经在朝真正的 objective/run/step execution ledger 发展

### 4.10 2026-03-16：前门策略层与模型路由治理开始系统化

关键文档：

- [2026-03-16_system_optimization_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-16_system_optimization_v1.md)
- [2026-03-16_model_routing_and_key_governance_blueprint_v1.md](/vol1/1000/projects/ChatgptREST/docs/2026-03-16_model_routing_and_key_governance_blueprint_v1.md)

`03-16` 是今天“要不要保留需求分析 / 前门策略 / funnel / preset / model routing”的关键起点。

这一天做出的东西包括：

- `skill_registry`
- `preset_recommender`
- `standard_entry`
- `deliverable_aggregator`

同时，模型路由治理蓝图明确指出：

- agent config
- `RoutingFabric`
- `ModelRouter`
- `LLMConnector`
- `/ask` route map

这些 authority 并不统一。

结论：

- 前门策略层不是今天才脑暴出来的
- 模型路由治理问题也不是“也许有点重复”，而是从 `03-16` 就被明确识别为结构性主问题

### 4.11 2026-03-17：public agent facade 与 cc-sessiond 同时起势，premium ingress/execution cabin 定位首次写清

关键文档与提交：

- `67a3fe9` `feat(agent): add v3/agent public facade routes`
- `4424165` `feat(mcp): add public agent MCP tools`
- `d27bc22` `feat(mcp): cut default surface to agent tools`
- `8faf145` `feat(cc-sessiond): full implementation with backend adapters and artifact persistence`
- [2026-03-17_premium_agent_ingress_and_execution_cabin_blueprint_v1.md](/vol1/1000/projects/ChatgptREST/docs/2026-03-17_premium_agent_ingress_and_execution_cabin_blueprint_v1.md)

这是今天很多概念纠缠的真正起点。

同一天发生了三件事：

1. `public agent facade` 开始成形
2. `public agent MCP` 开始收口成公共 surface
3. `cc-sessiond` 被当成 execution cabin 方向推进

而 `premium_agent_ingress_and_execution_cabin_blueprint_v1` 已经写得很清楚：

- `public agent facade` 应该是 premium deliberation ingress
- `cc-sessiond` 应该是 slow-path heavy execution cabin
- 不是所有请求都先进 `cc-sessiond`

结论：

- 你后来觉得 `cc-sessiond` 长歪，并不是因为当时没有正确定位
- 恰恰相反，定位当时写得相当清楚，真正的问题是后续实现没有完全按这个边界收住

### 4.12 2026-03-18 到 2026-03-20：近期收口线

这一段沿用 v1 结论，不重复展开：

- `public agent facade / public MCP`
- `premium ingress strategist`
- `direct live ask containment`
- `wait cancel`
- `cc-sessiond pool cleanup`
- `OpenClaw runtime history`
- `system state reconciliation`

相关文档已在 v1 中列出。

## 5. 从这条时间线里能看出的 5 个系统性事实

### 5.1 边界混乱不是因为“没想过”，而是因为多条正确主线同时推进

从 `03-07` 到 `03-17`，至少有 5 条都合理的主线在并行长：

- advisor runtime/runtime authority 收敛
- OpenClaw shell/runtime 重建
- memory/KB/EvoMap substrate
- controller/team execution ledger
- public agent facade / premium ingress / execution cabin

问题不是没有方向，而是这些方向后来缺了统一总规划。

### 5.2 `OpenClaw` 的 runtime substrate 身份很早就成立了

从 `03-08`、`03-09` 的 rebuild 文档开始，OpenClaw 就不是入口壳。

它一直在扮演：

- shell
- gateway
- session/channel continuity owner
- plugin runtime
- long-lived watchdog substrate

### 5.3 `OpenMind` 的身份比实现更清晰

从 `03-09` 开始就一直在说：

- OpenClaw 是 shell
- OpenMind 是 cognition substrate

但现实实现更多长在 `ChatgptREST` 里。

这不是否定 OpenMind，而是说明：

- **OpenMind 是系统身份和方法论**
- **ChatgptREST 是当前主要 runtime host**

### 5.4 知识层的真正老问题是 authority/path，不只是功能缺失

从 `03-10` 开始，文档已经反复在讲：

- dual-DB divergence
- shared resolver
- identity hardening
- canonical DB
- legacy fallback guard

这与今天我们发现的 `memory/KB` 运行态很薄、`EvoMap` 很厚完全呼应。

换句话说：

- 今天的知识层混乱不是“最近才坏了”
- 是一路带着 authority/path contract tension 演化过来的

### 5.5 `cc-sessiond/team runtime` 是实验资产，不是空壳，也不是主中心

从 `03-14` 到 `03-17`，这条线其实有连续演化：

- team control plane runtime
- controller team path
- cc-sessiond full implementation
- execution cabin blueprint

所以不能把它骂成“完全没做过”。

但从 `03-18` 到 `03-20` 的收口结果也说明：

- 它没有成为最稳定的主运行中心
- 今天更准确的定位仍然是：
  - 重要实验资产
  - 可回收对象与契约
  - 不应直接作为未来主中心

## 6. v2 对下一步规划的额外影响

相比 v1，这次往前追溯后，我会把下一步规划的前提再收紧一层：

### 6.1 不要把“现有东西很乱”误判成“现有东西都不成熟”

更准确的判断是：

- 很多东西其实已经成熟到第二阶段了
- 但它们之间缺统一 authority 和长期边界

### 6.2 下一步规划必须显式承认 3 条历史主线

后续任何蓝图都必须同时接住：

1. `OpenClaw shell/runtime` 主线
2. `ChatgptREST as current runtime host` 主线
3. `OpenMind as cognition identity/methodology` 主线

缺任何一条，都会再次回到“拼系统”的老路。

### 6.3 规划里必须把“历史 authority 冲突”单列成问题，不要只讲未来理想分层

尤其要单列：

- DB/path authority
- model routing authority
- runtime host authority
- session truth authority
- plugin/ingress authority

## 7. 这版追溯后的最终判断

把时间线拉回 `03-07` 之后，系统的真实图景更清楚了：

**你不是在一片废墟上重建，而是在几条都做到一半甚至两三成的强主线之间，缺了一个统一裁决层。**

所以今天最该做的不是再补一个局部功能，而是进入规划阶段时把这些主线关系重新排布清楚：

- 谁是 shell/runtime substrate
- 谁是 cognition identity
- 谁是 current runtime host
- 谁是 durable ledger
- 谁是 knowledge authority
- 谁只是实验资产

v1 解决的是“今天是什么状态”。  
v2 解决的是“今天为什么会变成这样”。
