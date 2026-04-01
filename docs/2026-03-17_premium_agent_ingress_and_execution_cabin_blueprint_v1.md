# Premium Agent Ingress And Execution Cabin Blueprint v1

日期：2026-03-17

## 1. 结论

`public agent facade` 不应被定义成“快入口”。

对 ChatgptREST 这套以 Web 自动化为核心、单次调用机会成本较高、答案质量要求较高的系统来说，它更合理的定位是：

- 一个 **premium deliberation ingress**
- 一个 **先想清楚再问** 的高成本入口
- 一个 **客户端只表达意图，但服务端负责把问题问对** 的统一入口

与此同时，`cc-sessiond` 不应被当成普通问答的默认执行路径，而应定位为：

- 一个 **execution cabin**
- 一个 **慢路径、重任务、强编排、多 agent 协作** 的执行平面
- 一个未来可承载 profile / `AGENTS.md` / MCP pack / skill pack / debate topology 的通用执行舱

因此，推荐架构不是“所有请求都先进 `cc-sessiond`”，而是三层分离：

1. **Ask Contract / Funnel 前置层**
2. **Execution 层**
3. **Post-Ask Review / EvoMap 复盘层**

`OpenClaw`、`Codex`、`Claude Code`、`Antigravity` 都应主要通过这一结构化入口与系统交互，而不是各自手搓 prompt、各自维护问题质量、各自决定模型。

## 2. 为什么要这样收敛

### 2.1 这个系统不是低成本聊天系统

这里的模型调用很多依赖：

- ChatGPT Web 自动化
- Gemini Web 自动化
- 深度研究与长等待
- 双模型对照
- 附件上传与上下文装配

因此它天然存在：

- 时延高
- 单次成本高
- 机会成本高
- 对“问题是否问对”非常敏感

结论：不能把它当成“随便问一句，系统秒给个差不多答案”的入口。

### 2.2 真正需要优化的不是“多几个 tool”

真正的问题不是 tool 太少，而是：

- 客户端在没有 ask contract 的情况下直接发自由文本
- 服务端没有强制做问题形成与需求确认
- prompt engineering 责任散落在客户端
- 问后没有统一复盘“问题质量 vs 模型匹配度 vs 答案质量”

所以最该优化的是：

- 问题形成
- 路由前 contract 冻结
- 服务端 prompt assembly
- 问后评审与反馈回写

## 3. 目标架构

### 3.1 总体分层

```text
Client Surface
  OpenClaw / Codex / Claude Code / Antigravity / CLI
        |
        v
Premium Agent Ingress
  Ask Contract + Funnel + Intake Checklist
        |
        v
Execution Router
  ChatGPT Web / Gemini Web / Consult / Image / Other premium substrates
        |
        v
Post-Ask Review Layer
  QA Inspector + Thinking QA + EvoMap writeback
        |
        v
Execution Cabin (slow path)
  cc-sessiond for long-running, multi-agent, systematized work
```

### 3.2 两条路径

#### Path A: Premium Deliberation Path

用于：

- 高质量问答
- 深度研究
- Pro / Gemini / consult 组合
- 高成本但不是“多 agent 长任务”的工作

执行特征：

- 先过 ask contract / funnel
- 再服务端组 prompt
- 再路由模型
- 最后做问后评审

#### Path B: Execution Cabin Path

用于：

- 长时间任务
- 多 agent 协作
- profile 驱动任务
- debate / critique / planner-reviewer-implementer
- 需要 durable session / artifact / event log / continuation 的任务

执行特征：

- 由 `cc-sessiond` 负责
- 可以不是代码开发，也可以是其他 agent 协作执行
- 不应成为普通问答默认路径

## 4. Ask Contract / Funnel 前置层

### 4.1 核心原则

在真正调用高成本模型之前，系统必须先回答：

- 这次到底要解决什么问题？
- 这次回答要支持什么决策？
- 当前上下文够不够？
- 哪些信息缺失？
- 该用哪种任务模板？
- 这次值得消耗一次 premium 调用吗？

### 4.2 最小 ask contract

每次 premium ask 至少要形成如下结构：

- `objective`
  - 目标是什么
- `decision_to_support`
  - 这次答案要支持什么决策
- `audience`
  - 谁来使用答案
- `constraints`
  - 时间、风险、范围、格式约束
- `available_inputs`
  - 当前已有材料
- `missing_inputs`
  - 还缺什么
- `output_shape`
  - 需要什么形式的结果
- `risk_class`
  - low / medium / high stakes
- `opportunity_cost`
  - 这次 premium 调用是否值得
- `task_template`
  - 归属哪类问题模板

### 4.3 现有可复用模块

仓里已有需求漏斗与 requirement analysis 的遗留实现，不应重造：

- [funnel.py](/vol1/1000/projects/ChatgptREST/chatgptrest/workflows/funnel.py)
- [pipeline.py](/vol1/1000/projects/ChatgptREST/chatgptrest/pipeline.py)
- [graph.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/graph.py)
- [dispatch.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/dispatch.py)
- [schemas.py](/vol1/1000/projects/ChatgptREST/chatgptrest/contracts/schemas.py)

现状判断：

- 这些模块还在
- 漏斗状态机和 ProjectCard 生成逻辑仍然有价值
- 但它们没有站到当前 public agent 的正门上

推荐动作：

- 不删除旧漏斗
- 把它收敛为新的 `Ask Contract / Funnel` 前置层
- 让 public agent ingress 默认先经过这一层，而不是直接吃自由文本

### 4.4 场景化模板

系统不应该把所有问题都当成同一类自由文本，而应按场景分治：

- research
- decision support
- code review
- implementation planning
- report generation
- image generation
- dual-model critique
- repair / diagnosis
- stakeholder communication drafting

每个场景都应有自己的：

- checklist
- required fields
- missing-info questions
- model routing preferences
- output rubric

## 5. 服务端 Prompt Engineering

### 5.1 原则

prompt engineering 应该放在服务端，不应该交给客户端。

客户端应该提交：

- 意图
- ask contract
- 结构化上下文
- 附件

服务端负责：

- contract normalization
- context assembly
- model-specific prompt adaptation
- guardrail injection
- output format contract

### 5.2 为什么必须服务端化

否则会出现：

- OpenClaw 一套 prompt
- Codex 一套 prompt
- Claude Code 一套 prompt
- Antigravity 一套 prompt

这会让质量策略、风控策略、问题模板、模型使用方式全部漂移。

### 5.3 具体要求

服务端 prompt assembly 至少应包含：

- role / perspective binding
- task template expansion
- output rubric
- available evidence summary
- explicit uncertainty handling
- model-specific strengths / weaknesses compensation
- answer formatting contract

## 6. Post-Ask Review / EvoMap 复盘层

### 6.1 核心理念

每一个高成本问题，在拿到答案之后，都应该被追问：

- 这个问题问得好不好？
- 这个答案答得怎么样？
- 如果换个问法，结果会不会更好？
- 效果不好，是问题形成有问题，还是模型选择有问题？
- 对于这个场景，下次应该如何问、如何选模型？

### 6.2 现有可复用模块

- [qa_inspector.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/qa_inspector.py)
- [thinking_qa.py](/vol1/1000/projects/ChatgptREST/chatgptrest/core/thinking_qa.py)
- [evomap.py](/vol1/1000/projects/ChatgptREST/chatgptrest/workflows/evomap.py)
- `chatgptrest/evomap/*`

这些部件已经能覆盖：

- 回答质量评审
- thinking-trace 质量评审
- 路由反馈与知识沉淀

### 6.3 应写回哪些信号

建议回写的最小字段：

- `question_quality`
- `contract_completeness`
- `missing_info_detected`
- `model_fit`
- `route_fit`
- `answer_quality`
- `actionability`
- `hallucination_risk`
- `prompt_improvement_hint`
- `template_improvement_hint`

### 6.4 目标

EvoMap 不只是记录“这次成没成功”，而是逐步学习：

- 什么问题该怎么问
- 什么模型适合什么任务
- 哪类 ask contract 容易失败
- 哪类模板更稳定

## 7. Public Agent Ingress 的重新定义

### 7.1 不再是“快入口”

`public agent facade` 的正确定位应改写为：

- premium ingress
- contracted ingress
- deliberation ingress

而不是：

- quick ask facade
- low-friction chat facade

### 7.2 它的职责

它应该负责：

- intake normalization
- ask contract gathering
- funnel / requirement clarification
- server-side prompt assembly
- premium routing
- post-answer review trigger

它不应该负责：

- 长任务多 agent 编排
- durable execution orchestration
- profile topology execution

这些属于 `cc-sessiond`

## 8. cc-sessiond 的重新定位

### 8.1 正确定位

`cc-sessiond` 不是普通问答路径，不应默认承接 OpenClaw 的所有请求。

它更适合作为：

- execution cabin
- slow-path orchestrator
- durable multi-agent session layer

### 8.2 它未来应支持的能力

- Claude Code backend
- profile-driven execution
- multi-agent debate
- planner / reviewer / implementer topology
- MCP pack selection
- skill pack selection
- `AGENTS.md` profile injection
- event log / artifact / checkpoint persistence

### 8.3 为什么不该放在 OpenClaw 侧配置

如果这些能力都堆在 OpenClaw 里：

- 配置会越来越散
- 复用会越来越差
- 客户端差异会越来越大

如果放到 `cc-sessiond`：

- profile 可复用
- tool pack 可复用
- skill pack 可复用
- 会话与工件可复用
- OpenClaw / Codex / Claude Code / Antigravity 只做入口壳

## 9. OpenClaw 的职责

OpenClaw 更适合作为：

- 交互壳
- 用户身份与 thread/account/agent identity 承载层
- 轻量入口编排层

而不是重执行平面本身。

推荐结构：

- OpenClaw 主路径 -> public premium ingress
- OpenClaw 慢路径 / 特殊任务 -> `cc-sessiond`

也就是：

- 普通 premium ask 不默认进 `cc-sessiond`
- 只有重任务、慢任务、多 agent 任务才进 `cc-sessiond`

## 10. 推荐实施顺序

### Phase 1: Re-anchor Public Agent Ingress

- 给 public agent ingress 加 ask contract schema
- 把旧 funnel 重新挂到入口前面
- 收敛客户端直接传自由文本的行为

### Phase 2: Server-side Prompt Assembly

- 建立 task-template registry
- 建立 model-specific prompt builder
- 禁止客户端手工拼核心 prompt

### Phase 3: Post-Ask Review

- 每次 premium ask 自动触发问后评审
- 写回 EvoMap
- 记录 question quality / model fit / route fit

### Phase 4: Elevate cc-sessiond

- 把 `cc-sessiond` 从 Claude Code session service 提升为 execution cabin
- 支持 profile / tool pack / skill pack / topology
- 支持 debate / critique / multi-agent orchestration

### Phase 5: Client Convergence

- OpenClaw 统一走 premium ingress 主路径
- 需要重任务时显式切到 `cc-sessiond`
- Codex / Claude Code / Antigravity 都共用同一 ask contract + review discipline

## 11. Definition of Done

这一轮不应只看“接口能不能调通”，而应看：

- premium ask 是否先过 ask contract
- funnel 是否真正站到入口前
- prompt engineering 是否已经服务端化
- 每次 premium ask 是否自动触发问后评审
- EvoMap 是否接收到 question-quality / model-fit / route-fit 信号
- `cc-sessiond` 是否被清晰限定为 execution cabin，而不是普通主路径
- OpenClaw 是否不再承担复杂执行配置本身

## 12. 一句话收束

未来目标不是“把更多 tool 暴露给客户端”，而是：

**把高成本问题先问对，把高质量执行放到服务端，把重任务协作沉到执行舱。**
