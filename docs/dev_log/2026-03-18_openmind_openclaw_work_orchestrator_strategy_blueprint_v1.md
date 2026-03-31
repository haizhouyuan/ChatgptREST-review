# 2026-03-18 OpenMind / OpenClaw / Work Orchestrator Strategic Blueprint v1

## 1. 这份蓝图要解决什么

当前系统不是“少一个组件”，而是同时存在 4 条彼此拉扯的方向：

- 想把 `OpenMind` 做成认知与知识中枢
- 想把 `OpenClaw` 做成强交互、强扩展、长期在线的入口壳
- 想把 `ChatgptREST` 从 web 自动化能力扩展成 agent interaction facade
- 想把 `ccrunner / cc-sessiond / agent teams` 做成执行层与多 agent 协作层

这些方向各自都有合理性，但如果不先做战略切分，最终会出现：

- 每个组件都在越界
- 每个组件都只做成一半
- 多任务、长任务、质量门禁、低盯盘能力都没有真正归属

这份蓝图的目标不是“给唯一答案”，而是把几条可走路线及其反对意见摆出来，然后明确推荐主线。


## 2. 当前真实业务重心

### 2.1 主战场不是“通用 agent 平台”

当前最有真实复用价值、最有沉淀价值的业务场景其实是两类：

- `planning`：人力资源规划、业务规划、会议纪要、调查报告、面试记录、管理材料
- `research`：主题研究、技术路线判断、背景资料整合、领导摘要、证据链研究

这两类任务的共性是：

- 强依赖历史文档与背景知识
- 强依赖口径一致性
- 强依赖 evidence pack / claims / 版本化产物
- 强依赖任务拆解、补问题、质量门禁
- 经常是多阶段、长周期、异步推进

### 2.2 `finbot` 是重要但相对独立的垂直线

`finbot + finagent` 是投研垂直产品，应继续单独演进，不适合作为主系统架构的牵引源。

它可以复用主系统中的：

- KB / memory
- task orchestration
- review / quality gates
- model routing

但不应反过来决定主系统的边界。


## 3. 先摆出几种互相冲突的意见

## 3.1 意见 A：`OpenMind` 做唯一主系统，其他都是外挂

主张：

- `OpenMind` 是大脑与治理层
- `OpenClaw` 是入口与在线外壳
- 新建 `Work Orchestrator` 作为执行控制面
- `ChatgptREST` 降级为专项 research / web lane
- `finbot` 独立

优点：

- 认知、执行、入口职责清楚
- 最符合当前真实高价值业务场景
- 长期最容易形成稳定的知识工作系统

反对意见：

- 这会让 `OpenMind` 继续承担很重的中枢角色，系统中心化较强
- 若 `OpenMind` 迟迟不稳定，其他能力都会被拖慢

我的判断：

- 这是最稳的主线
- 但需要给 `OpenMind` 严格限权：只做认知控制面，不亲自下场长执行


## 3.2 意见 B：`OpenClaw` 做总平台，其他能力都作为插件挂进去

主张：

- `OpenClaw` 有成熟的 gateway / session / extension / channel 生态
- 把 `OpenMind`、`ChatgptREST`、执行器都变成 OpenClaw 插件
- 用户入口、运行时、技能系统统一在 OpenClaw

优点：

- 交互体验与在线能力会很强
- 对“我不想盯 CLI”这个诉求特别友好
- 社区生态、扩展能力、持续在线都是现成优势

反对意见：

- `OpenClaw` 天然是入口壳和 assistant runtime，不是知识治理中枢
- 如果把业务知识、quality gates、requirements funnel 也塞进 OpenClaw，架构会变脏
- 容易演化成“外壳吞掉内核”

我的判断：

- `OpenClaw` 应该做 distribution shell，不该做业务大脑
- 可以做“默认交互与通知面”，不能做主系统中心


## 3.3 意见 C：`ChatgptREST` 继续长成统一 agent facade，再往下吃执行层

主张：

- `ChatgptREST` 已经有 jobs、controller、advisor、public facade、MCP
- 顺着 `/v3/agent/*` 再往下扩，就能成为通用 agent service

优点：

- 当前实现基础最多
- 对接 Codex/Claude/OpenClaw 的工具面已经很多

反对意见：

- 它的历史 DNA 是 web automation + job queue，不是知识工作操作系统
- 过去已经多次出现“功能越做越多，边界越来越不清”
- 容易继续把 research、agent facade、execution cabin、ops surface 混在一个仓里

我的判断：

- `ChatgptREST` 应降级成专项 lane，而不是未来总平台
- 否则旧问题会继续复发


## 3.4 意见 D：先不谈平台，直接把 `finbot` 做成最强垂直产品

主张：

- 垂直产品最容易形成闭环
- 投研天然适合研究、知识、监控、异步任务
- 先用 `finbot` 验证 orchestration 与 review 体系

优点：

- 更容易做出成果
- 有清晰用户与业务边界

反对意见：

- 会让主系统架构被投研语义绑死
- `planning / research` 的通用工作流仍然没人收敛

我的判断：

- `finbot` 应作为验证场，不应成为主系统战略起点


## 4. 推荐主线

推荐采用 **意见 A 的骨架**，但吸收 B 和 D 的长处。

也就是：

- `OpenMind`：认知控制面
- `Work Orchestrator`：执行控制面
- `OpenClaw`：在线入口、触达、通知、长期在线壳
- `ChatgptREST`：deep research / web automation / long async lane
- `finbot`：独立垂直应用

一句话：

**做知识型工作的智能操作系统，而不是再造一个全能 agent 平台。**


## 5. 为什么必须引入一个更强的执行控制面

`Runner Bridge` 的问题是名字和心智都太轻。

你真正要的不是简单“桥接 CC 和 Codex”，而是：

- 多任务并发管理
- 多类型任务编排
- 长任务低盯盘运行
- 角色分工与角色责任
- 任务暂停 / 恢复 / 取消 / 接力
- 质量门禁与 stopline
- 主动监控 blocked / drift / low-quality 结果
- 人类只在关键时刻被叫醒

因此更合适的名字不是 `Runner Bridge`，而是：

- `Work Orchestrator`
- 或 `Execution Cabin`
- 或 `Task Control Plane`

本蓝图统一使用 `Work Orchestrator`。


## 6. 新架构中的角色关系

## 6.1 `OpenMind` 负责什么

`OpenMind` 只负责认知与治理，不负责长执行。

应该收进 `OpenMind` 的能力：

- 需求管理
- 意图分析
- funnel / clarify / worth-it 判断
- 任务拆解与计划生成
- 场景分类
- 模型路由
- 技能路由
- KB / memory / EvoMap
- review rubric / output contract 生成

不该由 `OpenMind` 直接承担的能力：

- 长时多 agent 执行
- runtime 监工
- 大量并发任务队列与恢复


## 6.2 `Work Orchestrator` 负责什么

`Work Orchestrator` 是一个真正的任务执行控制面。

它负责：

- 接受 `OpenMind` 产出的 `TaskSpec` / `ScenarioPack` / `ExecutionPlan`
- 创建 durable `Run`
- 按任务类型分配角色和执行模板
- 管理并发、优先级、超时、checkpoint、resume
- 持续监督质量与进度
- 触发人工确认与通知
- 把 artifact / status / review 结果回传给 `OpenMind`

它不负责：

- 解释用户最终意图
- 维护 KB 世界观
- 长期知识演化


## 6.3 `OpenClaw` 负责什么

`OpenClaw` 是默认人机交互与在线入口壳。

它负责：

- 飞书 / IM / chat / web 入口
- 通知、提醒、checkpoint 交互
- skill / extension 装载
- 长期在线 presence

它不负责：

- 认知路由主逻辑
- 业务场景的门禁规则
- 执行控制面账本


## 6.4 `ChatgptREST` 负责什么

`ChatgptREST` 作为专项能力轨道存在：

- ChatGPT / Gemini web 深度调研
- 需要网页自动化的特殊场景
- 长异步结果收集

它不再负责：

- 总 public facade
- 通用 agent runtime
- 主执行控制面


## 7. 多 agent 协作怎么做才不会再次失控

不要先支持“任意 team topology”。

先只支持 **模板化团队**。

建议先落 3 套：

### 7.1 Planning Pack

角色：

- `intake_analyst`
- `context_researcher`
- `planner`
- `reviewer`
- `publisher`

用途：

- 业务规划
- 会议纪要整理
- 面试记录归档
- 管理材料与汇报文案


## 7.2 Research Pack

角色：

- `scoper`
- `parallel_scout`
- `synthesizer`
- `skeptic`
- `final_reviewer`

用途：

- 主题研究
- 技术路线判断
- 背景资料整合
- 领导摘要


## 7.3 Execution Pack

角色：

- `strategist`
- `implementer`
- `reviewer`

用途：

- CC / Codex 协作执行
- 交互式开发任务
- 重工具链任务

### 7.4 关键约束

这里的“角色”不等于“都是真人或都是真 agent”。

角色可以映射到：

- 确定性程序
- 单次 LLM 调用
- `ChatgptREST` research lane
- `CC`
- `Codex`
- 人类 checkpoint

这比“先做一个通用 agent teams 平台”更现实，也更可控。


## 8. 需求管理、模型路由、funnel、skills 应该怎么安放

## 8.1 需求管理

不要再把它理解成一个平行系统。

它是 `OpenMind` intake 层的数据契约：

- `Request`
- `Clarification`
- `TaskSpec`
- `Acceptance`
- `WorthItDecision`


## 8.2 Funnel

`funnel` 应该是 `OpenMind` 的任务入口治理器，而不是独立产品。

它负责回答：

- 这个需求值不值得投入
- 这个需求缺什么信息
- 现在是执行还是先补问题
- 该走哪一个 scenario pack


## 8.3 模型路由

模型路由不能成为用户面心智。

它应该是：

- `OpenMind` 中的 policy service
- 根据 task type / risk / quality bar / budget 做决策

不是：

- 用户自己手工选模型
- 每个工具面都暴露 provider-first contract


## 8.4 Skill 体系

技能必须拆成两层，不然会变成垃圾抽屉。

### A. Scenario Skills

面向业务场景：

- planning report
- meeting digest
- interview packet
- theme research
- leader summary

内容包括：

- intake checklist
- clarify template
- output contract
- review rubric
- publish gate

### B. Runtime Skills

面向执行器：

- CC coding task packet
- Codex repo review task packet
- ChatgptREST deep research task
- browser / docs / OCR / publish adapters

内容包括：

- tool contract
- runtime hints
- retry / timeout policy
- artifact mapping


## 9. 质量怎么保障，而不是靠你盯 CLI

质量不能靠“多开几个 agent 自己看”。

必须制度化。

建议 `Work Orchestrator` 内建 5 类质量门：

- `Structure Gate`
  - 输出格式、字段、章节是否完整
- `Evidence Gate`
  - 是否有足够的来源、路径、原始证据
- `Decision Gate`
  - 能不能下结论，还是只能给 `needs_more`
- `Risk Gate`
  - 是否触发 stopline / escalation
- `Publish Gate`
  - 是否达到可归档、可发出、可写入 KB 的标准

同时要有一个 `supervisor` 能力，不是生成内容，而是负责：

- 监测 blocked / timeout / no-progress
- 检测低质量产出
- 按策略重试、换 lane、叫人

这才是真正的“低盯盘但不低质量”。


## 10. 技术实现上的取舍

## 10.1 不要再手搓一个 scheduler + registry 半成品

如果真的重做 `Work Orchestrator`，就应该直接建立在成熟 durable workflow 内核上。

推荐组合：

- `OpenMind`：LangGraph
- `Work Orchestrator`：Temporal

理由：

- `OpenMind` 适合认知图、clarify、review、memory / KB writeback
- `Temporal` 适合多任务、长任务、并发、resume、signals、timers、operator-grade execution

## 10.2 反对意见

也有一个强反对意见：

- 直接上 `Temporal` 可能会增加工程门槛
- 对单人开发来说，运维复杂度不小

我的判断：

- 如果还想再活 6 个月以上，就值得
- 如果只求短期验证，也可以先做“轻量执行控制面 + 明确契约”，但这只能是过渡态


## 11. 明确哪些事现在不要做

- 不要继续扩旧 `cc-sessiond`
- 不要继续把 `ChatgptREST` 当总平台
- 不要先做无限泛化的 agent team builder
- 不要让 `OpenClaw` 吃掉知识中枢
- 不要让 `finbot` 反向决定主系统架构
- 不要把 skill 体系做成无边界插件市场


## 12. 6 个月路线图

## 阶段 1：战略收口

- 固定 4 层架构名词
- 冻结旧 `cc-sessiond` 扩张
- 明确 `OpenMind` / `OpenClaw` / `ChatgptREST` / `Work Orchestrator` 的职责边界

## 阶段 2：先做一条标杆链路

只做 1 条真正高频链路：

- `planning report end-to-end`
  或
- `theme research end-to-end`

这条链路必须包含：

- intake
- clarify
- planning
- execution
- review
- publish / archive

## 阶段 3：建立 `Work Orchestrator`

- 任务模型
- role 模型
- run / checkpoint / artifact 模型
- supervisor / notify 机制
- 3 套固定团队模板

## 阶段 4：把 `OpenClaw` 接成默认外壳

- checkpoint / approval / wakeup / notify
- 不再要求你盯 CLI

## 阶段 5：专项 lane 接入

- `ChatgptREST`
- `CC`
- `Codex`
- 其他 runtime

## 阶段 6：再考虑抽象成更泛化平台

只有当模板化团队已经反复验证后，才值得进一步抽象。


## 13. 最后给一个最尖锐的判断

你之前的问题不是“想太多”本身。

真正的问题是：

- 在没有一个稳定主心骨之前，就同时做平台、入口、执行、垂直应用
- 在没有一条标杆业务链路闭环之前，就想把所有能力抽象成通用层

所以这次最重要的战略取舍不是“再选一个新组件”，而是：

**先承认主战场是知识型工作的 planning / research。**

然后围绕这个主战场，建立：

- `OpenMind` 认知控制面
- `Work Orchestrator` 执行控制面
- `OpenClaw` 在线入口壳
- `ChatgptREST` 专项 deep research lane

剩下的东西，都围绕它们服务。


## 14. 待进一步争论的问题

这份 v1 蓝图里，仍有几个值得专门开评审的问题：

- `Work Orchestrator` 是放在 ChatgptREST 仓内先做，还是独立成新模块 / 新 repo
- `OpenMind` 和 `Work Orchestrator` 的 state boundary 怎么切
- `OpenClaw` 的 skills 与 `Scenario Skills` 的关系怎么定义
- 第一条标杆链路到底选 `planning` 还是 `research`
- `Temporal` 是立即采用，还是先用更轻的过渡执行层

这些都不影响主战略方向，但会影响落地节奏。
