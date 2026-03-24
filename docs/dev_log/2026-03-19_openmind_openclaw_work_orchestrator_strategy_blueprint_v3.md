# 2026-03-19 OpenMind OpenClaw Work Orchestrator Strategy Blueprint v3

## 1. Executive Decision

这版蓝图不是基于想象中的“全新系统”，而是基于 2026-03-19 当前代码现实重写。

核心结论只有 6 条：

1. `OpenClaw` 不能再被降级成“入口壳”。它已经是现成的常驻运行底座，必须被充分利用。
2. `OpenMind` 仍然应该是认知控制面，但当前真正运行中的 OpenMind 主要实现并不在独立 `openmind` 仓库，而是在 `ChatgptREST` 的 `advisor + controller` 代码里。
3. `ChatgptREST` 不应该继续被包装成“未来总中台”，但它现在仍然是最完整的 slow-path advisor/controller/deep-research 运行面。
4. `Work Orchestrator` 在 Phase 1 不应该先做成一个新的重服务。先把它定义为一层清晰的对象模型和策略层，落在 `OpenMind + OpenClaw + ChatgptREST` 之上。
5. `planning` 与 `research` 是主场景，必须优先于“任意 team topology 的通用多智能体平台”。
6. `需求分析` 要保留，但要收缩成前门的 `Intake / Clarify / Scope`，而不是独立膨胀成一套重产品。

一句话定稿：

`OpenClaw` 负责持续在线和持续执行，`OpenMind` 负责想清楚和做对，`ChatgptREST` 负责当前最成熟的 slow-path cognition/execution lane，而 `Work Orchestrator` 先作为共享控制面模型落地，不急着先造新 daemon。

## 2. What This Blueprint Is Optimizing For

主系统只优化两类高价值知识型工作：

- `planning`
  - 业务规划
  - 人力资源规划
  - 会议总结
  - 调查报告
  - 面试记录
  - 版本化协作文档
- `research`
  - 主题研究
  - 技术路线分析
  - 器件/赛道追踪
  - 证据链综合
  - 结论与不确定性管理

这些场景有共同特征：

- 强依赖历史文档与知识库
- 需要澄清、限定范围、明确输出物
- 需要角色化校验，而不是单次回答
- 需要低盯盘长任务能力
- 需要明确的可交付物与验收标准

`finbot` 继续作为独立垂直线演进，不定义主系统架构。

## 3. Non-Goals

以下内容明确不是本阶段目标：

- 不做新的“全能 agent 平台”
- 不再把 `cc-sessiond` 扶成未来核心
- 不在 Phase 1 做任意 team topology
- 不把 `OpenClaw` 重新实现一遍
- 不把 `ChatgptREST` 再包装成通用操作系统
- 不把 `需求分析` 做成大而全 standalone product

## 4. Code Reality Inventory

### 4.1 OpenClaw is already a real runtime substrate

`OpenClaw` 当前已经具备的不是“聊天入口”而是完整运行底座：

- Gateway 是所有 messaging surface 的唯一事实源，负责 WebSocket 控制面、event push、node/device 连接与鉴权  
  见 `/vol1/1000/projects/openclaw/docs/concepts/architecture.md`
- Session 由 gateway 持有，是 source of truth；客户端不应自持 session state  
  见 `/vol1/1000/projects/openclaw/docs/concepts/session.md`
- `sessions_spawn` 已经提供隔离子任务、后台执行、结果回传和自动归档  
  文档见 `/vol1/1000/projects/openclaw/docs/tools/subagents.md`  
  实现见 `/vol1/1000/projects/openclaw/src/agents/tools/sessions-spawn-tool.ts`
- subagent 生命周期和恢复逻辑已经有 registry  
  见 `/vol1/1000/projects/openclaw/src/agents/subagent-registry.ts`
- heartbeat 是现成的长时 watcher/runtime 能力，不是概念稿  
  见 `/vol1/1000/projects/openclaw/src/infra/heartbeat-runner.ts`
- cron/webhook/control-ui/openresponses/tools-invoke 都已具备  
  见：
  - `/vol1/1000/projects/openclaw/src/cron/service.ts`
  - `/vol1/1000/projects/openclaw/src/gateway/openresponses-http.ts`
  - `/vol1/1000/projects/openclaw/src/gateway/tools-invoke-http.ts`

因此，`OpenClaw` 的正确定位应该是：

- 常驻交互底座
- session/channel continuity owner
- 多 agent 和 subagent runtime
- heartbeat/cron/webhook 背景运行面
- user-facing notification / control 面

不应该让它承担：

- planning/research 方法论
- task spec 治理
- KB/EvoMap 策略
- slow-path quality gates 本身

### 4.2 OpenMind standalone repo is not the runtime center today

独立 `openmind` 仓库目前仍然偏薄：

- README 里写的是理想架构  
  `/vol1/1000/projects/openmind/README.md`
- `openmind/openmind/` 下面主要还是 package skeleton

这意味着：

- `OpenMind` 作为系统身份是成立的
- 但当前实际运行中的 OpenMind，大部分已经长在 `ChatgptREST` 内部

这是后续蓝图必须正面承认的事实，不能再把“目标身份”和“当前实现”混成一件事。

### 4.3 ChatgptREST already hosts the practical OpenMind runtime

当前仓库里，真正工作的认知/规划/slow-path 主链主要在这些文件：

- `advisor graph`
  - `/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/graph.py`
- `task spec`
  - `/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/task_spec.py`
- `standard entry`
  - `/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/standard_entry.py`
- `funnel graph`
  - `/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/funnel_graph.py`
- `public agent facade`
  - `/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py`
- `advisor API`
  - `/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor_v3.py`
- `durable controller`
  - `/vol1/1000/projects/ChatgptREST/chatgptrest/controller/engine.py`

这些代码已经形成了现实中的“OpenMind runtime”：

- `graph.py`
  - 已经是 LangGraph 封装
  - 节点是 `normalize -> kb_probe -> analyze_intent -> route_decision -> branch`
  - 说明系统已经不是纯 REST wrapper，而是认知图在运行
- `task_spec.py`
  - 已经有 `IntentEnvelope` 和 `TaskSpec`
  - 说明“统一任务对象”这条路是对的
  - 但当前字段太粗，只够做雏形
- `standard_entry.py`
  - 已经在尝试统一 Codex/MCP/其他入口
  - 但本质上还是 `preset/skill/quality` 的轻包装
- `funnel_graph.py`
  - 适合 planning 类慢任务
  - 但不适合作为所有请求的默认前门
- `routes_agent_v3.py`
  - 当前 public facade 已经不是单纯透传
  - 已有 `AskContract -> AskStrategyPlan -> compiled_prompt -> clarify`
- `controller/engine.py`
  - 已经是 durable run/work/checkpoint/artifact ledger
  - 具备 `job/effect/team` 三种 execution kind

### 4.4 Existing OpenClaw integration is already real

`OpenClaw -> ChatgptREST` 不是未来式，而是已经存在两条接法：

1. 现行主桥：
   - `/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-advisor/index.ts`
   - `/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-advisor/README.md`

这条桥的特征：

- 工具名是 `openmind_advisor_ask`
- 直接调用 `POST /v3/agent/turn`
- 会把 `session_id/account_id/thread_id/agent_id/user_id` 往下透传
- 还会把 OpenClaw runtime identity 合并进 `context`

2. 历史/并行桥：
   - `/vol1/1000/projects/ChatgptREST/chatgptrest/integrations/openclaw_adapter.py`

这条桥的特征：

- 通过 MCP HTTP 工具调用 `sessions_spawn/sessions_send/session_status`
- 更接近旧式 session-tool adapter

这意味着这次重构不是 greenfield：

- 现成主桥已经存在
- 但当前有两套接法并存
- 必须明确收敛目标，而不是继续叠加第三套

### 4.5 Current team runtime path is transitional, not the center

当前 `team` 执行链真实存在，但还不够成熟，不能拿来当总体架构核心：

- controller 的 `execution_kind == team` 分支在  
  `/vol1/1000/projects/ChatgptREST/chatgptrest/controller/engine.py`
- `ControllerEngine._dispatch_route_to_team()` 会：
  - 解析 `team_spec/topology`
  - 构造 `CcTask`
  - 启后台 thread
  - 调 `cc.dispatch_team(...)`
- team 账本在  
  `/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/team_control_plane.py`
- 执行器在  
  `/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/cc_native.py`

这条线的现实定位应该是：

- 有价值的实验资产
- 适合保留其对象和账本思路
- 但当前不应主导 `planning/research` 架构

## 5. Architecture v3

### 5.1 Final framing

目标架构调整为：

```text
User / Feishu / Cron / Webhook
    -> OpenClaw Gateway + Agent Runtime
    -> OpenMind Cognitive Front Door
    -> Scenario Policy + Work Orchestrator Model
    -> Execution Lanes
    -> Artifacts / KB / EvoMap / Notifications
```

但必须注明“当前实现落点”：

```text
OpenClaw
    -> openmind-advisor plugin
    -> ChatgptREST /v3/agent/turn
    -> advisor/controller runtime
    -> route to deep research / direct job / transitional team lane
```

所以：

- `OpenMind` 是逻辑层和系统身份
- `ChatgptREST` 是当前最成熟的 `OpenMind runtime host`
- `OpenClaw` 是交互和持续运行底座
- `Work Orchestrator` 在 Phase 1 是逻辑控制层，不先独立拆出新服务

### 5.2 Layer responsibilities

#### OpenClaw

负责：

- 会话、渠道、身份和推送连续性
- 主 agent 与 subagent 运行
- heartbeat / cron / webhook 触发
- control UI、operators、background presence
- 在无需用户盯盘时替用户盯运行状态

不负责：

- 复杂任务方法论
- KB/EvoMap 决策
- planning/research 质量门禁
- 全局 task spec 语义

#### OpenMind

负责：

- intake / clarify / scope
- 需求分析与意图分析
- planning / research 场景策略
- funnel/route/model policy
- evidence threshold / acceptance policy
- KB grounding / memory / EvoMap signal 解释

当前实现主要落在 `ChatgptREST advisor + controller`。

#### Work Orchestrator

Phase 1 定义：

- 不是独立 daemon
- 是共享对象模型 + shared policy layer
- 落在 `OpenMind + OpenClaw + ChatgptREST` 之上

它负责的抽象包括：

- 任务对象
- 场景模板
- 角色链
- 低盯盘 watch policy
- quality gates
- checkpoint policy
- artifact contract

只有在对象模型稳定、场景包稳定之后，才考虑抽成独立 service。

#### ChatgptREST

负责：

- public slow-path facade
- advisor/controller durable run
- deep research / web execution lane
- async jobs / artifacts / provenance
- 当前最成熟的 OpenMind runtime host

不负责：

- 抢占 OpenClaw 的 session/runtime 地位
- 直接成为未来统一总中台

#### Finbot

保持独立产品线：

- 可以消费 OpenMind/ChatgptREST 能力
- 但不反过来定义主系统的通用架构

## 6. The Most Important Design Choice

### 6.1 Work Orchestrator should start as a logical layer, not a new daemon

如果现在马上开新服务，很大概率又会复制出一个：

- 自己维护状态
- 自己维护 watcher
- 自己再接入口
- 自己再做 artifact
- 最后再和 OpenClaw / ChatgptREST state 冲突

这正是旧 `cc-sessiond` 类问题的重演。

因此 Phase 1 的硬约束是：

- 不新建一个“功能很全但状态边界不清”的 orchestrator 服务
- 先统一对象模型
- 先让 `OpenClaw` 和 `ChatgptREST` 各归其位
- 先让场景包跑通真实业务

### 6.2 Extraction rule

只有满足下面 4 个条件，才允许把 `Work Orchestrator` 从逻辑层抽成独立服务：

1. `planning` 与 `research` 两个场景包都已经稳定运行
2. `Task Intake Spec / RunLink / Artifact contract / Watch policy` 已冻结
3. OpenClaw runtime 和 ChatgptREST controller 的职责边界已稳定
4. 新服务不会重复持有 session/channel state

不满足这 4 条，就不抽。

## 7. Unified Control Objects

这次重构最该先做的不是 UI，不是 team，不是更多插件，而是统一对象。

### 7.1 RuntimeIdentity

来源：

- `OpenClaw session_id`
- `OpenClaw session_key`
- `agent_id`
- `account_id`
- `thread_id`
- `user_id`

作用：

- 作为任务和执行链的稳定身份锚点
- 明确“结果要回到哪条会话、哪个入口”

当前已有基础：

- `openmind-advisor` 插件已经在透传这些身份字段

### 7.2 IntentEnvelope

当前已有：

- `chatgptrest/advisor/task_spec.py`

保留方向，但要扩充定义。

### 7.3 Task Intake Spec

建议新增为主对象，替代当前过粗的 `TaskSpec` 热路径字段。

最小字段建议：

- `task_id`
- `scenario`
  - `planning | research | quick | coding | ops`
- `objective`
- `deliverable`
- `audience`
- `scope_in`
- `scope_out`
- `inputs_available`
- `inputs_missing`
- `evidence_requirement`
- `constraints`
- `acceptance_criteria`
- `watch_policy`
- `runtime_identity`
- `attachments`
- `source`
- `priority`

说明：

- `Task Intake Spec` 是前门产物
- 不是最终执行 plan
- 也不是最终 artifact

### 7.4 ScenarioPack

建议新增：

- `PlanningPack`
- `ResearchPack`
- 以后才考虑 `CodingPack`

每个 pack 必须定义：

- intake checklist
- clarify rules
- route policy
- role chain
- quality gates
- publish readiness
- watcher policy

### 7.5 RunLink

必须新增一个映射对象，把三层 ID 明确串起来：

- `openclaw_session_key`
- `openclaw_thread_id`
- `task_id`
- `controller_run_id`
- `job_id`
- `artifact_root`

没有 `RunLink`，后面所有低盯盘监控、回写、通知、恢复都会继续碎。

### 7.6 QualityGate

建议只先做 3 类：

- `clarity_gate`
- `evidence_gate`
- `delivery_gate`

不要上来做十几类花哨 rubric。

### 7.7 WatchPolicy

这是这次必须补上的对象，因为你的真实痛点就是“不想盯 CLI，但也不能糊”。

字段建议：

- `watch_mode`
  - `foreground | background | notify_only`
- `max_silence_minutes`
- `checkpoint_notify`
- `blocked_notify`
- `completion_notify`
- `requires_human_for_publish`

## 8. Requirement Analysis: Keep It, But Bound It

### 8.1 Why it must exist

结合 `planning` 仓库现有资料，`planning` 任务天然要求：

- 唯一口径
- 生效版本
- 证据回指
- gate / RACI / signoff
- 输出物定义

相关资料：

- `/vol1/1000/projects/planning/00_入口/总入口.md`
- `/vol1/1000/projects/planning/00_入口/当前版本总览.md`
- `/vol1/1000/projects/planning/00_入口/每次交互后的判断与核验简表.md`
- `/vol1/1000/projects/planning/00_入口/唯一口径底座.md`
- `/vol1/1000/projects/planning/docs/规划_Pro复审闭环工作流.md`

如果没有前置需求分析，系统会把含糊问题放大成含糊结果。

### 8.2 Why it must not become its own giant product

如果把需求分析做成独立重系统，会出现两个问题：

- 所有请求都要走重 intake，速度和用户体验都会崩
- 它会再和 `funnel`、`strategist`、`TaskSpec` 发生职责重叠

### 8.3 Final policy

- `planning`：必须做完整 `Intake / Clarify / Scope`
- `research`：做轻量任务定义
- `quick`：默认跳过
- `coding`：默认只在高风险/正式交付物时触发 clarify

## 9. Scenario Packs

### 9.1 Planning Pack

适用：

- 业务规划
- 会议纪要成稿
- 面试记录整理
- 版本化报告
- 需要明确对外口径的材料

流程建议：

1. intake
2. clarify
3. scope freeze
4. KB / prior-doc grounding
5. outline / structure proposal
6. evidence collection
7. synthesis draft
8. review gate
9. publish-ready delivery

最低产物要求：

- 目标
- 范围 in/out
- 主要依据
- 当前有效版本引用
- 未决问题
- 下一步建议

### 9.2 Research Pack

适用：

- 主题研究
- 技术路线分析
- 赛道/器件调研
- 深度问题证据链

流程建议：

1. question framing
2. scope definition
3. source/evidence threshold
4. scout / gather
5. synthesis
6. skeptic / uncertainty pass
7. final memo

最低产物要求：

- 研究问题
- 核心结论
- 证据条目
- 反例/不确定性
- 后续建议

### 9.3 Coding Pack

本阶段不作为主包，但保留接口。

原因：

- 你的主战场不是 coding 平台
- coding lane 仍然需要，但不该先反向定义总架构

## 10. Role Strategy

不要一开始做任意 team topology。

先固定少量稳定角色：

- `main`
  - 对人主入口
  - 持有会话连续性
- `planning`
  - 负责 planning pack
- `research`
  - 负责 research pack
- `ops`
  - 负责低盯盘 watcher / reminder / escalation

其他角色先做成临时 role chain，不先做常驻 agent：

- `reviewer`
- `skeptic`
- `publisher`
- `coder`

理由：

- 常驻 agent 太多会带来配置、权限、记忆和路由复杂度
- 你当前真正需要的是稳定场景，而不是角色炫技

## 11. Execution Lanes

### 11.1 Lane policy

只保留 4 类 lane：

- `openclaw_local`
  - 普通对话与轻任务
- `chatgptrest_slowpath`
  - public agent facade
  - advisor/controller
  - deep research
  - durable async jobs
- `openclaw_subagent`
  - 并行小任务
  - 低盯盘 watcher
  - background scout / follow-up
- `coding_external`
  - CC/Codex 等 heavy coding runtime

### 11.2 Key decision

`OpenClaw` 不负责替代 `ChatgptREST` 的 slow-path cognition。  
`ChatgptREST` 也不负责替代 `OpenClaw` 的常驻 runtime。

这两个边界必须固定。

## 12. Concrete Integration Contract

### 12.1 Ingress contract

所有入口最终归一为：

```json
{
  "runtime_identity": {
    "session_id": "...",
    "session_key": "...",
    "account_id": "...",
    "thread_id": "...",
    "agent_id": "...",
    "user_id": "..."
  },
  "intent_envelope": {
    "source": "openclaw",
    "raw_text": "...",
    "attachments": []
  },
  "task_intake_spec": {
    "scenario": "planning",
    "objective": "...",
    "deliverable": "...",
    "evidence_requirement": "kb+web",
    "watch_policy": {
      "watch_mode": "background"
    }
  }
}
```

### 12.2 Recommended surface choice

主桥统一成：

- `OpenClaw plugin -> POST /v3/agent/turn`

而不是继续扩 `openclaw_adapter.py` 那套 MCP session-tool 主链。

`openclaw_adapter.py` 的建议定位：

- 兼容层
- 特殊工具性桥接
- 非主 ingress

### 12.3 Current `/v3/agent/turn` role

当前已经具备的前门顺序应该保留并增强：

1. normalize ask contract
2. strategist plan
3. compiled prompt
4. clarify gate
5. controller dispatch

要改的不是主顺序，而是输入对象要更结构化。

## 13. Concrete Ownership Matrix

### OpenClaw owns

- `session_key`
- channel delivery
- user-facing continuity
- subagent runtime
- heartbeat / cron / webhook triggers
- background reminders and notifications

### OpenMind owns

- `task_id`
- `Task Intake Spec`
- scenario decision
- clarify / scope / acceptance
- evidence requirement
- KB/EvoMap policy

### ChatgptREST owns

- `run_id`
- `job_id`
- durable execution status
- provenance
- artifacts / answer payloads
- current slow-path controller runtime

### Shared via Work Orchestrator model

- `RunLink`
- `WatchPolicy`
- `QualityGate`
- `ScenarioPack`

## 14. Concrete Sequence Flows

### 14.1 Planning flow

```text
User/Feishu
  -> OpenClaw main agent
  -> openmind_advisor_ask
  -> /v3/agent/turn
  -> Task Intake Spec (planning)
  -> clarify if required
  -> controller slow-path
  -> draft / review / publish-ready output
  -> result returned to same OpenClaw session
  -> optional DingTalk publish
```

关键点：

- 用户永远只看一条会话
- 结构化 slow-path 在后台跑
- notify/checkpoint 由 OpenClaw 负责送回

### 14.2 Research flow

```text
User
  -> OpenClaw
  -> OpenMind front door
  -> Task Intake Spec (research)
  -> route = chatgptrest_slowpath
  -> deep research / hybrid
  -> evidence-rich memo
  -> skeptic pass
  -> result returned to same session
```

### 14.3 Low-attention monitoring flow

```text
Long task submitted
  -> WatchPolicy says background
  -> OpenClaw heartbeat/cron tracks run silence and checkpoints
  -> if blocked: notify user
  -> if complete: summarize back to original session
```

重点：

- 不另造 watcher daemon
- 优先用 OpenClaw heartbeat/cron/subagent

## 15. What To Keep, What To Freeze, What To Deprecate

### Keep

- `openmind-advisor` OpenClaw plugin
- `/v3/agent/turn` strategist mainline
- advisor/controller durable run ledger
- `IntentEnvelope` / `TaskSpec` 方向
- OpenClaw subagent / heartbeat / cron runtime
- `team_control_plane` 中的账本思路

### Freeze

- 独立 `openmind` 仓库作为当前 runtime 主体的幻想
- `Work Orchestrator` 先做新 daemon 的冲动
- 任意 team topology 先行的想法

### Deprecate

- `openclaw_adapter.py` 作为主 ingress
- 旧 `cc-sessiond` 作为未来主执行内核
- `team child executor` 作为 planning/research 主线

## 16. Concrete Implementation Plan

### Phase 1A: Unify the front-door object model

目标：

- 不动大架构，先把对象统一起来

修改建议：

1. `chatgptrest/advisor/task_spec.py`
   - 保留 `IntentEnvelope`
   - 新增 `TaskIntakeSpec`
   - 新增 `RuntimeIdentity`
   - 新增 `RunLink`
   - 新增 `WatchPolicy`
2. `chatgptrest/advisor/standard_entry.py`
   - 不再只返回轻量 `dispatch_params`
   - 改为产出 `TaskIntakeSpec`
3. `chatgptrest/api/routes_agent_v3.py`
   - 显式接收 `task_spec`
   - 若外部未传，则 server 合成
   - 持久化到 session/context/provenance
4. 新增测试：
   - `tests/test_task_intake_spec.py`
   - `tests/test_routes_agent_v3_task_spec.py`

退出条件：

- 任一入口都能落出稳定 `task_id + scenario + watch_policy`

### Phase 1B: Tighten OpenClaw integration

目标：

- 让 OpenClaw 成为真正的 runtime substrate，而不是只发一条 ask

修改建议：

1. `openclaw_extensions/openmind-advisor/index.ts`
   - 继续保留 `openmind_advisor_ask`
   - 增加对结构化 `taskSpec` 的支持
   - 继续透传 runtime identity
2. `openmind-advisor` 说明文档更新
3. 统一约定：
   - 主 ingress 走 plugin -> `/v3/agent/turn`
   - 不再优先走旧 MCP session adapter

退出条件：

- OpenClaw 发出的 slow-path ask 能稳定追踪到 `task_id/run_id/job_id`

### Phase 1C: Add scenario packs

目标：

- 先只打透 `planning` 和 `research`

修改建议：

1. 新增 `chatgptrest/advisor/scenario_packs.py`
2. 把 `planning` / `research` 的：
   - clarify policy
   - evidence policy
   - acceptance policy
   - watch policy
   固定下来
3. 让 `routes_agent_v3.py` 或 advisor graph 在 route 前先吃 scenario pack

退出条件：

- planning 和 research 两类请求进入不同但稳定的 slow-path

### Phase 1D: Use OpenClaw as watcher

目标：

- 实现“我不盯 CLI，但质量不能烂”

修改建议：

1. 不新增 watcher 服务
2. 优先用 OpenClaw：
   - heartbeat
   - cron
   - subagents
3. 建立从 `RunLink` 到通知行为的映射

退出条件：

- blocked / checkpoint / completion 都能自动回到原会话

### Phase 2: Decide whether Work Orchestrator needs extraction

只有当以下情况出现时才抽独立 service：

- `ScenarioPack` 已稳定
- `RunLink` 已稳定
- watcher policy 已稳定
- `OpenClaw` 与 `ChatgptREST` 的职责边界已稳定

否则继续保持逻辑层实现。

## 17. Risks

### Risk 1: Build another half-finished middle layer

规避：

- 不先起新 daemon
- 先统一对象

### Risk 2: Underuse OpenClaw again

规避：

- 明确把 session/watcher/runtime 放回 OpenClaw

### Risk 3: Overload ChatgptREST again

规避：

- 只让它做 slow-path cognition/controller lane
- 不让它接管所有 runtime concerns

### Risk 4: Requirement analysis grows without bound

规避：

- 只保留 `Intake / Clarify / Scope`
- 只对 planning/research 做强前门

## 18. Immediate Next Steps

下一轮工程上最值得先做的，不是 UI，不是 agent team，而是下面 5 件：

1. 在 `task_spec.py` 里补齐 `TaskIntakeSpec + RuntimeIdentity + RunLink + WatchPolicy`
2. 把 `standard_entry.py` 从轻量 `dispatch_params` 升级成真正的 intake front door
3. 让 `/v3/agent/turn` 接受并回传结构化 `task_spec`
4. 明确 `OpenClaw plugin -> /v3/agent/turn` 是唯一主 ingress
5. 落 `PlanningPack` 与 `ResearchPack` 两个场景包

## 19. Final Recommendation

这次不要再从“我还缺一个更强的执行器”出发。

正确的重构顺序是：

1. 承认 `OpenClaw` 已经是 runtime substrate
2. 承认 `ChatgptREST advisor/controller` 才是当前运行中的 OpenMind
3. 把 `Work Orchestrator` 先收成对象模型和策略层
4. 只围绕 `planning` 和 `research` 两个主场景落功能
5. 等对象稳定、边界稳定之后，再决定是否抽独立 orchestrator service

这条路线的优点不是“最炫”，而是：

- 最符合当前代码现实
- 最少重复造轮子
- 最能把你已经投入的 OpenClaw/ChatgptREST 资产真正用起来
- 最不容易再做出一个天天爆问题的半成品中台
