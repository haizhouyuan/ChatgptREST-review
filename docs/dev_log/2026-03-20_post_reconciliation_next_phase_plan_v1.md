# 2026-03-20 Post-Reconciliation Next Phase Plan v1

## 1. 计划定位

这份计划建立在以下两份对账文档之上：

- [2026-03-20_system_state_reconciliation_master_audit_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_system_state_reconciliation_master_audit_v1.md)
- [2026-03-20_system_state_reconciliation_master_audit_v2.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_system_state_reconciliation_master_audit_v2.md)

它的作用不是继续讨论“系统应该像什么”，而是把下一阶段真正该做的事收成一个可执行的顺序。

本计划追求 4 个目标：

1. 先统一 authority，再恢复主链。
2. 先把 `planning / research` 两个主场景打透，再谈通用平台化。
3. 充分利用 `OpenClaw` 现有 runtime substrate，而不是再造一层同类 runtime。
4. 对已经做过一半的模块做收敛，不再继续平行长新中心。

## 2. 先锁死的判断

### 2.1 四层主关系

下一阶段一律按下面这个关系看系统：

- `OpenClaw`
  - 常驻 gateway
  - session/channel continuity owner
  - background runtime substrate
- `OpenMind`
  - 认知身份、方法论、前门 contract、任务语义
- `ChatgptREST`
  - 当前最成熟的 slow-path runtime host
  - 当前最厚的 durable execution ledger 所在地
- `Finagent`
  - 独立垂直系统

### 2.2 不能再继续含糊的 5 个结论

1. `OpenClaw` 不是入口壳。
2. `ChatgptREST` 不是未来总中台。
3. `OpenMind` 不是当前独立仓实现中心，而是系统身份与当前 runtime 方法论。
4. `EvoMap` 是当前最厚的知识资产之一。
5. `cc-sessiond / team runtime` 是实验资产与可回收契约，不是下一阶段主中心。

### 2.3 本阶段不做的事

- 不重启“通用多 agent 平台”大工程
- 不把 `cc-sessiond` 扶成未来内核
- 不先做图库/多模态知识库
- 不让 `Finagent` 反向定义主系统架构
- 不先追求任意 team topology
- 不再新造一个和 `OpenClaw` 重叠的长期运行服务

## 3. 本阶段的总目标

本阶段不是“把一切都重写”，而是完成 3 个结果：

1. **Authority 清晰化**
   - 路径、数据库、模型路由、入口、telemetry 的唯一口径写清并落到代码/配置

2. **主链恢复**
   - `OpenClaw -> OpenMind front door -> ChatgptREST runtime host` 的一条最小闭环重新稳定跑通

3. **场景收敛**
   - 只围绕 `planning` 和 `research` 做对象模型、场景包、技能使用和验收口径

## 4. 阶段规划

## Phase 0: Authority Freeze

### 目标

先把“谁是事实源”定死，不再在 split-brain 状态下继续开发。

### 为什么先做这个

当前最危险的问题不是少功能，而是：

- `memory / KB / EvoMap` 口径不一致
- model routing authority 不一致
- OpenClaw / ChatgptREST / Advisor 入口语义不一致
- telemetry 当前还有 live failure

如果这一步不先做，后面任何恢复、上线、场景化都会继续建立在错口径之上。

### 本阶段任务

1. 写一份 **authority matrix v1**
   - 路径 authority
   - DB authority
   - route authority
   - model routing authority
   - session truth authority
   - telemetry authority

2. 对知识层做一个明确决策：
   - `EvoMap` 继续作为 canonical knowledge graph / retrieval substrate
   - `OpenMind memory/KB` 是保留为轻量前门层，还是要做迁移/并表/降级说明

3. 对模型路由做一个明确决策：
   - 只保留一个 canonical routing contract
   - `RoutingFabric / ModelRouter / routing_engine / LLMConnector fallback` 的主从关系写死

4. 对运行态 env / path 做一个明确决策：
   - 运行面统一使用哪个 `HOME`
   - `~/.home-codex-official/.openmind` 是否继续作为 live state
   - 哪些路径是 legacy residue，只读不再写

5. 对 telemetry/ingest 做一个明确决策：
   - 修 `openmind-telemetry flush failed`
   - 修 closeout `404 /v2/telemetry/ingest`
   - 统一 OpenClaw/OpenMind/ChatgptREST 的 telemetry target

### 交付物

- `authority_matrix_v1.md`
- `knowledge_authority_decision_v1.md`
- `routing_authority_decision_v1.md`
- `telemetry_contract_fix_v1.md`

### 验收

- 所有关键运行态路径都能指向明确的 single source of truth
- 不再存在“文档说这套是主库，但当前 runtime 实际在用另一套”的情况
- OpenClaw gateway telemetry 不再持续刷失败

## Phase 1: Front Door Contract Freeze

### 目标

把 `OpenMind` 前门收成一个稳定契约，让后续所有入口都走同一套任务语义。

### 为什么排在第二

当前已经证明：

- 需求分析/前门策略不是空白
- `TaskSpec / standard_entry / preset_recommender / funnel / ask_contract / strategist` 都存在

问题不在“没有”，而在“没有收敛成一个 canonical front door contract”。

### 本阶段任务

1. 定义统一前门对象：
   - `IntentEnvelope`
   - `Task Intake Spec`
   - `Ask Contract`
   - `Acceptance Spec`

2. 场景只保留 4 类：
   - `quick`
   - `planning`
   - `research`
   - `coding`

3. 统一入口：
   - OpenClaw plugin
   - public agent facade
   - MCP/public tools
   - Feishu ingress

4. 明确字段和澄清策略：
   - `objective`
   - `decision_to_support`
   - `output_shape`
   - `constraints`
   - `available_inputs`
   - `missing_inputs`
   - `evidence_required`
   - `acceptance`

5. 决定 `funnel` 的地位：
   - 不再作为所有请求默认前门
   - 保留为重型 `planning/research` 入口的增强调度器

### 交付物

- `front_door_contract_v1.md`
- `task_intake_spec_v1.json`
- `scenario_taxonomy_v1.md`
- `front_door_route_matrix_v1.md`

### 验收

- 从 OpenClaw、public facade、Feishu 进入的请求，都能映射到同一套结构化对象
- 不再存在“同一类请求在不同入口被不同语义处理”的情况

## Phase 2: Runtime Host Recovery

### 目标

重新恢复一条最小但可信的主链：

`OpenClaw -> OpenMind front door -> ChatgptREST runtime host -> artifact/result -> OpenClaw session`

### 为什么排在第三

因为当前 `ChatgptREST runtime` 处于停机状态。  
不先做前两步 authority 和 contract freeze，直接重启服务只会恢复旧的混乱。

### 本阶段任务

1. 先恢复最小服务集，不一次全开：
   - `chatgptrest-api`
   - `chatgptrest-mcp` 视需要
   - 最小 worker 组合
   - 必要时 `feishu-ws`

2. 验证三条最小主链：
   - OpenClaw main -> public agent facade -> ChatgptREST -> answer
   - OpenClaw main -> planning ask -> clarification / completion
   - OpenClaw main -> research ask -> deep lane / report result

3. 做最小 live acceptance pack：
   - 非 trivial
   - 不走 synthetic
   - 每条链路有 artifact 和 session evidence

4. 明确不恢复的旧链：
   - legacy bare MCP tool direct usage
   - `cc-sessiond` 作为默认执行入口

### 交付物

- `runtime_recovery_runbook_v1.md`
- `openclaw_to_chatgptrest_acceptance_pack_v1.md`
- `live_acceptance_evidence_bundle`

### 验收

- 最小主链 live 可跑
- 入口 contract、执行 path、回写路径一致
- 没有再次出现 low-value live ask 漏发或 synthetic 污染

## Phase 3: Knowledge Runtime Rebalance

### 目标

把当前知识层不对称问题转成明确设计，而不是继续悬空。

### 核心问题

当前真实情况是：

- `EvoMap` 很厚
- `OpenMind memory/KB` 很薄

下一步必须决定这是：

- 临时状态，需要补厚 memory/KB
- 还是目标状态，即 `EvoMap` 主厚、`memory/KB` 轻量化

### 我的建议

本阶段先按下面的角色分工设计：

- `memory`
  - 用户偏好、局部指令、会话级与跨会话轻量记忆
- `KB`
  - 高质量文档和交付物索引
- `EvoMap`
  - 大规模 graph/episode/evidence 底座与演化信号

不要强行把三者合并成一库。

### 本阶段任务

1. 给 `memory / KB / EvoMap` 写 role contract
2. 为 `planning / research` 定义 retrieval priority
3. 决定哪些内容写回 KB，哪些只写 EvoMap，哪些写 memory
4. 明确当前 `memory/KB` 是否需要一次 live backfill

### 交付物

- `knowledge_runtime_contract_v1.md`
- `retrieval_priority_matrix_v1.md`
- `writeback_policy_v1.md`

### 验收

- 任何一类信息都能回答：
  - 存哪
  - 谁读
  - 谁写
  - 为什么不存到另一层

## Phase 4: Scenario Packs for Planning / Research

### 目标

围绕你真正高价值的两类工作，把“多角色协作 + 低盯盘 + 质量门禁”收成稳定场景包。

### 本阶段任务

#### Planning Pack

角色建议：

- `main`
  - 对人主入口
- `intake`
  - task intake / clarify / scope
- `planner`
  - 结构化交付物
- `reviewer`
  - 证据、边界、验收检查
- `ops/watcher`
  - 低盯盘状态跟踪

产物建议：

- planning brief
- decision memo
- meeting digest
- interview note
- structured report bundle

#### Research Pack

角色建议：

- `scoper`
- `researcher`
- `synthesizer`
- `skeptic/reviewer`
- `publisher`

产物建议：

- research brief
- evidence pack
- claim ledger
- final research note

### 技能体系策略

此阶段技能只分两类：

- `Scenario Skills`
  - 面向 planning/research 的模板和流程
- `Runtime Skills`
  - 面向 OpenClaw / ChatgptREST / browser / report / document lane 的执行能力

不做第三类“大 marketplace”。

### 交付物

- `planning_pack_v1.md`
- `research_pack_v1.md`
- `scenario_skill_matrix_v1.md`

### 验收

- planning/research 两个场景至少各有 1 条真实工作流跑通
- 能在不盯 CLI 的情况下，通过 OpenClaw session/heartbeat/cron 完成长任务推进和回报

## Phase 5: Heavy Execution and Team Runtime Decision

### 目标

不是马上重做 execution cabin，而是等前四阶段收口后，再决定是否需要独立 `Work Orchestrator` 或新的 heavy execution service。

### 本阶段为什么必须后置

因为当前对这块已经有三份现实资产：

- `controller objective/run/step ledger`
- `team_control_plane`
- `cc-sessiond`

如果前面没先把 authority、front door、knowledge、scenario 收住，直接在这里开工，极大概率再长出第四套执行中心。

### 本阶段要回答的问题

1. `Work Orchestrator` 需要是独立服务，还是逻辑层？
2. `team_control_plane` 应保留为账本，还是升级为中心控制面？
3. `cc-sessiond` 是适合作兼容壳、runtime adapter，还是直接退场？
4. `OpenClaw subagent/runtime` 与 `controller/team` 的关系怎么定？

### 只有在满足以下条件时才进入本阶段

- authority freeze 已完成
- front door contract 已完成
- 最小 runtime host 主链已恢复
- planning/research scenario packs 已至少各跑通一条真实工作流

## 5. 下一阶段的先后顺序

顺序必须固定：

1. `Authority Freeze`
2. `Front Door Contract Freeze`
3. `Runtime Host Recovery`
4. `Knowledge Runtime Rebalance`
5. `Scenario Packs`
6. `Heavy Execution Decision`

不能跳步。

最重要的一条纪律：

**在 Phase 0 到 Phase 2 期间，不得再新增新的执行中心、新的 facade、新的 session service。**

## 6. 这阶段该停掉的习惯

1. 不再把每个局部问题都解释成“需要新服务”。
2. 不再把 `OpenClaw` 降级成单纯 bot shell。
3. 不再把 `ChatgptREST` 想象成未来唯一总中台。
4. 不再让 `model routing` 在多个地方各写一份。
5. 不再在 knowledge 层继续混用路径与 authority。
6. 不再在 `planning/research` 之外先追求通用多 agent 炫技。

## 7. 立即行动清单

如果现在开始执行，这一周最值得做的 8 件事是：

1. 写 `authority_matrix_v1`
2. 写 `knowledge_runtime_contract_v1`
3. 写 `routing_authority_decision_v1`
4. 修 `openmind-telemetry flush failed`
5. 修 closeout telemetry ingest `404`
6. 定 `front_door_contract_v1`
7. 定 `scenario_taxonomy_v1`
8. 恢复最小 `OpenClaw -> ChatgptREST` live 主链并做 acceptance

## 8. 最终结论

下一步不是“继续补功能”，而是：

**先用三步把系统收成可规划状态：**

1. 统一 authority  
2. 统一前门 contract  
3. 恢复最小主链

之后再围绕 `planning / research` 两个主场景做稳定场景包。  
只有这两类工作流真实跑顺之后，才有资格再讨论新的 heavy execution center 或通用多 agent 平台。
