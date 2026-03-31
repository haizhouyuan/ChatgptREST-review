# Agent Harness 工程调研最终综合结论 v4

更新时间：2026-03-31

## 0. 文档定位与版本关系

这是本主题的**最终综合结论 v4**。

本版与此前版本的关系如下：

- `v1`：主参考源识别错误，作废。
- `v2`：已重做，但未完整吸收 ChatGPT Pro 正式长答，作废。
- `v3`：核心方向正确，但对外部原文的逐篇吸收、对本地半成品模块的边界刻画、以及对 `Task Harness Layer` 的工程化落点仍不够硬，**被本版 supersede**。

本版不是“继续补几条建议”，而是基于以下四层证据重新冻结最终判断：

1. 外部原文审计包
2. ChatGPT Pro 正式长答
3. Gemini Deep Think 长答
4. 本地 `ChatgptREST + planning` 代码与文档现状

---

## 1. 审计范围与方法

### 1.1 外部原文审计包

本版不再只引用链接，而是以本地审计包为主要阅读入口。

审计包目录：

- `/vol1/1000/projects/planning/docs/sources/agent_harness_2026-03-31/`
- `/vol1/1000/projects/planning/docs/sources/agent_harness_2026-03-31/source_registry.json`

已逐篇落盘的原文包括：

- `anthropic_harness.md`
- `anthropic_evals.md`
- `claude_prompting.md`
- `openai_harness_engineering.md`
- `openai_codex_harness.md`
- `openai_responses_background.md`
- `inngest_harness.md`
- `inngest_durable_execution.md`
- `microsoft_sre_harness.md`
- `langchain_deep_agents.md`
- `langgraph_platform_ga.md`

这些文件都带有：

- `source_url`
- `fetched_at`
- `extract_method`

因此本版判断不是“凭记忆复述文章”，而是基于已落盘原文重读后的再判断。

### 1.2 外部长答材料

#### ChatGPT Pro

不再使用浏览器中途可见片段，而是以 authoritative child job 的正式长答为准：

- `/vol1/1000/projects/ChatgptREST/artifacts/jobs/ed787d3706a1421bb6e4a1911701f138/answer.md`

#### Gemini Deep Think

完整长答文件：

- `/tmp/gemini_agent_harness_answer_v3.txt`

注意：

- Gemini 没有读到全部本地 brief，但读到了若干核心代码文件。
- 因此它适合作为结构性架构评审，不适合作为本地系统状态的唯一解释源。

### 1.3 本地代码重读范围

本版重新核验并纳入判断的关键本地模块如下：

#### `planning`

- `/vol1/1000/projects/planning/scripts/planning_bootstrap.py`

#### `ChatgptREST`

- `/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/task_intake.py`
- `/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/task_spec.py`
- `/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/artifact_store.py`
- `/vol1/1000/projects/ChatgptREST/chatgptrest/eval/evaluator_service.py`
- `/vol1/1000/projects/ChatgptREST/chatgptrest/eval/decision_plane.py`
- `/vol1/1000/projects/ChatgptREST/chatgptrest/quality/outcome_ledger.py`
- `/vol1/1000/projects/ChatgptREST/chatgptrest/core/completion_contract.py`
- `/vol1/1000/projects/ChatgptREST/chatgptrest/cognitive/context_service.py`
- `/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/work_memory_manager.py`
- `/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/work_memory_importer.py`

### 1.4 判断方法

本版判断遵循以下顺序：

1. 原文先读
2. 再看 Pro / Gemini 长答如何抽象
3. 再回到本地代码核对哪些判断真能落地
4. 最后才做综合归纳

因此，本版会显式区分：

- 原文直接支持的结论
- 外部长答提供的高层抽象
- 本地代码已存在的真实能力
- 我基于多源综合得到的系统性判断

---

## 2. 逐源重读后的关键启示

### 2.1 Anthropic: Harness design for long-running application development

这篇文章最重要的不是“多 agent”，而是三条更硬的结构性原则：

1. **长任务的真正负载点在执行中间层。**
   不是最终答案，不是历史记忆，而是执行过程中：
   - 规格冻结
   - chunk contract
   - skeptical evaluation
   - file-backed handoff

2. **planner / generator / evaluator 的拆分价值，不在“多角色”本身，而在职责隔离。**
   - planner 负责把模糊目标变成可测的当轮合同
   - generator 负责生成
   - evaluator 负责怀疑、找错、拉回

3. **harness 必须是适应性的，而不是教条性的。**
   Anthropic 后来移除了部分 sprinting，但不是因为 harness 不重要，而是因为在特定模型能力上，某些 scaffolding 不再是 load-bearing。  
   真正要学的是：
   - 任何 harness 组件都应被看作关于当前模型边界的可测假设
   - 不应把 sprint、planner、evaluator 固化成宗教

对本地系统的直接启发是：

**你最需要的不是“更多记忆”，而是一个能在模型边界附近动态收紧和放松的任务控制层。**

### 2.2 Anthropic: Demystifying evals for AI agents

这篇文章把 eval harness 讲得比大多数工程文更完整，尤其重要的是：

- `task`
- `trial`
- `grader`
- `transcript`
- `outcome`
- `evaluation harness`

这几个概念被严格区分开了。

对你当前系统最重要的启发有三条：

1. **任务质量最终看 outcome，不看 transcript。**
   这和你当前已经做得很好的 `completion_contract` 很接近，但要再往前走一步：  
   对长任务而言，最终可信度应首先来自**被评估并 promoted 的 task outcome**，然后才由 `completion_contract` 对外发布。

2. **eval suite 是持续资产，不是一次性验证。**
   这意味着后面你要做的不只是 acceptance，而是：
   - 任务级回归库
   - reference solutions
   - pass@k / pass^k
   - human calibration

3. **grader 必须是多类型组合。**
   对你的系统，后续 evaluator 不应只跑单测，还应组合：
   - code-based grader
   - browser/API outcome grader
   - rubric/LLM grader
   - operator review

### 2.3 Claude Docs: Prompting best practices

Claude 文档真正值钱的不是 prompt 模板，而是这套 workflow 观：

- fresh window 优于无限压缩
- 状态要落盘而不是只留在会话
- `tests.json`、`init.sh`、progress files 是一等工件
- git / 文件系统是长期协作的稳定承载体

这和 Anthropic harness 主文是互相印证的：  
**长任务不该靠“继续聊天”，而该靠“重新进入一个由文件系统显式表达的任务状态”。**

### 2.4 OpenAI: Harness engineering: leveraging Codex in an agent-first world

这篇文章对你最关键的价值，不在“zero manual code”口号，而在两条非常硬的工程纪律：

1. **`AGENTS.md` 只能是 map，不该是百科全书。**
2. **repo-local docs/artifacts 才是 system of record。**

OpenAI 明确指出：

- Google Docs
- 聊天记录
- 脑中的共识

对 agent 都是不可见的。  
这和你现在把 authority、backfill、work-memory 往 repo 里拉的方向完全一致。

但这篇文章还多给了一个重要启发：

**execution plans 应当是 first-class versioned artifacts。**

这直接推动本版结论从 `TaskSpec` 上升为：

- `TASK_SPEC`
- `EXECUTION_PLAN`
- `TASK_STATE`
- `ACCEPTANCE_CHECKS`
- `FINAL_OUTCOME`

这些都应成为正式工件，而不只是临时文档。

### 2.5 OpenAI: Unlocking the Codex harness

这篇文章最该吸收的，是：

**长任务必须有 server-authoritative lifecycle。**

OpenAI 用：

- `thread`
- `turn`
- `item`

把跨客户端、可恢复、可重连的对话生命周期固化为 server 侧协议。

对你系统的直接启发是：

当前 `session_id / thread_id / trace_id / logical_task_id` 虽然已经很多，但还没有形成真正的**task-authoritative lifecycle**。  
你下一步应该补的是：

- `task_id`
- `attempt_id`
- `chunk_id`
- `task_state`

而不是继续依赖会话级标识来串长任务。

### 2.6 OpenAI: New tools and features in the Responses API

真正值钱的是 `background mode` 这个运行观：

- 长任务默认应该是 async
- 可以 inspect
- 可以 catch-up
- 可以恢复

这意味着：

**你不能再把同步问答面硬撑成长任务控制面。**

这条会直接影响本版对 `Task Harness Layer` 的定义：  
它必须带有 durable execution 语义，而不只是 planner-wrapper。

### 2.7 Inngest: Your Agent Needs a Harness, Not a Framework

这篇文章最强的贡献，是把“harness”从抽象理念落回到生产现实：

- checkpoint
- retries
- exact-once / idempotency
- human-in-the-loop pause
- external event resume
- concurrency control

它提醒你：

**长任务的难点不只是推理，而是恢复、暂停、串行化、回放和治理。**

### 2.8 Inngest: Durable Execution

这篇和上一篇一起读，结论更明确：

**durable execution 不是配套能力，而是 harness 核心。**

对 ChatgptREST 的直接落点是：

- singleton concurrency per `task_id`
- checkpointed execution
- pause / resume
- background run
- external signal / operator approval
- idempotent replay

### 2.9 Microsoft: Harness Engineering for Azure SRE Agent

微软这篇最值得吸收的是：

**文件系统既是工作台，也是预算管理原语。**

它把 filesystem 的地位拔得非常高：

- 不是附件目录
- 不是副产品
- 而是 agent 可以导航、可以推理、可以交接、可以审计的主空间

这对你当前系统是一个直接推动：

你不应只做 `artifact_store`，还应做**任务工作区 contract**。

### 2.10 LangChain / LangGraph: Deep Agents + Platform GA

这两份材料共同强调：

- 长任务需要持久化图状态
- 需要 checkpoint
- 需要 rewind / rerun / edit
- 需要 virtual filesystem / skill / memory 的明确分层

它们不是要你照搬 LangGraph，而是进一步证明：

**Task Harness Layer 必须同时具备：**

- 状态化执行
- 可恢复
- 可编辑
- 可重放
- 明确的 artifact/workspace 约束

---

## 3. ChatGPT Pro、Gemini 与本地代码的收敛与分歧

### 3.1 三路收敛点

ChatGPT Pro、Gemini 和本地代码核验，在大方向上高度收敛到以下判断：

1. 当前系统已经有很强的：
   - authority plane
   - recall plane
   - delivery plane

2. 当前系统真正缺的是：
   - task-run control plane
   - task-level eval harness
   - durable execution plane

3. 因此下一阶段不该再主要投入在：
   - 更大的 memory
   - 更复杂的 retrieval
   - 更厚的 prompt

而应该投入在：

- 任务初始化
- 任务账本
- chunk contract
- evaluator gate
- durable execution
- final outcome publication

### 3.2 Pro 的关键贡献

Pro 长答最有价值的地方，是把现有系统重排成了一条更正确的链：

`intake -> frozen context snapshot -> task spec -> contract -> execution -> evaluation -> promotion -> completion publication -> durable memory distillation`

这比 `v3` 更重要，因为它明确了：

- `completion_contract` 和 `work_memory` 都不应位于控制链最上游
- 它们都应是**promoted outcome 之后**的下游发布/蒸馏层

### 3.3 Gemini 的关键贡献

Gemini 的价值在于提醒：

- `completion_contract` 解决的是**回答 finality**
- `work_memory` 解决的是**跨会话 durable context**
- 但长任务真正缺的是：
  - `Task`
  - `TaskPlan`
  - `EvaluationReport`
  - `OperatorLog`

这个提醒是对的，而且和本地代码现状对得上。

### 3.4 我对两者的独立修正

外部长答的方向基本对，但本地代码重读后，我要做两条修正：

1. **不要把本地系统说得过于空白。**
   真实情况是：
   - 你已经有不少 task-related 半成品
   - 问题不是“从零没有”
   - 而是“这些能力分散在 intake / artifact / evaluator / outcome / memory / completion 六层，没有被重组成一个正式 task plane”

2. **不要把 Task Harness 理解成又一层 planner 包装。**
   真正要补的不是一个 planner，而是：
   - task control plane
   - durable execution plane
   - task-level eval harness

---

## 4. 当前本地系统：哪些是真底座，哪些是半成品，哪些是错位

### 4.1 已经做对的底座

#### 4.1.1 `completion_contract + canonical_answer`

这条线已经是当前系统最成熟的地方之一。

它解决的是：

- 对外发布 finality
- authoritative answer publication
- answer-state gating
- consumer 对齐

这条线不该推翻。

#### 4.1.2 `work_memory durable objects`

当前 `Decision Ledger / Active Project Map / Post-call Triage / Handoff` 的设计方向是对的。  
加上 importer、governance、review queue、query-aware retrieval，这条线已经是结构化 durable context 底座，不该推翻。

#### 4.1.3 `planning backfill + importer`

这条线的价值是：

- 历史 planning 资料不再只是 archive
- 它们已经能进入结构化 durable memory

这条线也不该推翻。

### 4.2 真实存在但还没被提升为 task plane 的半成品

#### 4.2.1 `task_intake.py`

这是当前系统里最接近“任务前门”的 canonical object。

它已经有：

- versioned intake schema
- source / ingress_lane / scenario / output_shape
- acceptance spec
- evidence requirement
- task/session/account/thread/agent/role identity

所以它不是一个无关辅助件，而是：

**未来 Task Harness 的前门归一化对象。**

#### 4.2.2 `task_spec.py`

这不是一个真正的 task harness spec，而是：

**旧 carrier 模型向 canonical intake 的兼容桥。**

它说明本地系统已经意识到不能维护两套前门 schema，但它还没上升到：

- chunk contract
- task state
- evaluator gate
- outcome promotion

#### 4.2.3 `artifact_store.py`

这是一个很重要、但在 `v3` 里没有被充分强调的底座：

- content-addressable
- provenance-tracked
- `task_id + step_id + producer`

这意味着：

**你已经有可作为任务工件底层存储的 content-addressable artifact store。**

后面真正要做的不是另造一套 artifact backend，而是把它正式纳入 task harness。

#### 4.2.4 `evaluator_service.py`

它已经能把 QA inspector 报告转成结构化 `EvaluatorResult`。  
但它当前边界很清楚：

- 它是 adapter
- 它不是独立的任务级 evaluator runtime

所以它是可复用底座，但还不是你要的“skeptical evaluator”完整实现。

#### 4.2.5 `decision_plane.py`

它当前明写是：

**observer-only improvement proposal generator**

这点很关键。  
它说明本地系统已经开始做：

- promotion proposal
- suppression proposal

但它还不是：

- 真正的 promotion authority
- 任务 gate owner

#### 4.2.6 `outcome_ledger.py`

它当前是：

**execution outcome observer ledger**

它已经有：

- `run_id`
- `logical_task_id`
- route/provider/channel/session
- retrieval refs
- artifact refs

这说明 outcome 观察账本已经存在。  
但它当前仍然是：

- observer ledger
- 不是 promoted task outcome ledger

这也是为什么本版会提出：  
下一步不是重写 outcome，而是把它**上移并加硬成 `FinalOutcome` 上游账本**。

### 4.3 当前真正缺失的不是 memory，而是 task control plane

把上面这些半成品放在一起看，得到的结论很清楚：

你当前系统不是“没有 task 相关能力”，而是：

- 有 intake
- 有 spec bridge
- 有 artifact store
- 有 evaluator adapter
- 有 proposal plane
- 有 outcome ledger
- 有 completion publication
- 有 work memory

但它们还没有被组织成：

**一个 server-authoritative 的 task lifecycle。**

---

## 5. v4 的最终综合结论

### 5.1 不是只加一个 Task Harness Layer

`v3` 的主要问题，是把结论压缩成了“加一个 Task Harness Layer”。  
这个方向没错，但还不够硬。

本版的最终结论更精确：

**ChatgptREST 下一阶段应该新增的，不只是一个 Task Harness Layer，而是一个由三部分组成的任务运行中枢：**

1. **Task Control Plane**
2. **Durable Execution Plane**
3. **Task-Level Eval Harness**

### 5.2 四个真相平面

按本版最终判断，你的系统应该明确分成四个真相平面：

1. **Authority Plane**
   - planning authority docs
   - canonical domain truth
   - historical backfill / decision supersession

2. **Task Plane**
   - live task workspace
   - task state
   - chunk contracts
   - progress / bug / evaluation / handoff

3. **Delivery Plane**
   - `completion_contract`
   - `canonical_answer`
   - authoritative delivery publication

4. **Memory Plane**
   - durable work-memory objects
   - decision/project/handoff distillation

当前系统最缺的是第 2 层，而不是第 4 层。

### 5.3 重新排序后的正确链路

本版冻结的推荐主链是：

`task intake -> frozen task context -> task spec -> execution plan -> chunk contract -> execution -> evaluator report -> promotion decision -> final outcome -> completion publication -> durable memory distillation`

这个顺序的意义在于：

- **scope** 先被冻结
- **执行** 再展开
- **promotion** 由 evaluator/operator 决定
- **completion** 只负责发布
- **memory** 只负责蒸馏 durable conclusions

### 5.4 generator 不应自证完成

这是本版最强的架构判断之一。

以后 generator 最多只能：

- 生成变更
- 写 progress
- 提 amendment request

它不能：

- 自己宣布 task complete
- 自己宣布 chunk pass
- 自己直接产出 durable memory conclusion

### 5.5 work memory 的角色要降回正确位置

当前 work memory 很强，但它的正确位置是：

- 提供 durable context
- 提供 bootstrap inputs
- 接收 promoted outcome 的蒸馏结果

它**不该继续承担 task scope reconstruction 的主工作**。

也就是说：

**task 继续靠 live retrieval 重建 scope** 这件事，应该被正式淘汰。

---

## 6. ChatgptREST Task Harness 的完整集成蓝图

### 6.1 总原则

不是推翻现有系统，而是重排与上移。

保留：

- `task_intake`
- `task_spec` compatibility bridge
- `artifact_store`
- `evaluator_service`
- `decision_plane`
- `outcome_ledger`
- `completion_contract`
- `work_memory`

新增的是：

- 一个正式的 `task_harness/` 模块族

### 6.2 建议新增模块

建议新增：

- `chatgptrest/task_harness/models.py`
  - `Task`
  - `TaskAttempt`
  - `TaskChunk`
  - `TaskState`
  - `TaskMode`
- `chatgptrest/task_harness/contracts.py`
  - `TaskContextLock`
  - `ExecutionPlan`
  - `ChunkContract`
  - `AcceptanceCheck`
- `chatgptrest/task_harness/workspace.py`
  - task workspace 目录布局
  - artifact manifest
  - workspace validation
- `chatgptrest/task_harness/runtime.py`
  - task state machine
  - checkpoint / resume
  - concurrency lock
- `chatgptrest/task_harness/planner.py`
  - 从 `task_intake + frozen context` 生成 `TaskSpec + ExecutionPlan`
- `chatgptrest/task_harness/executor.py`
  - 消费 chunk contract
  - 执行 generator lane
  - 只允许 contract-bounded execution
- `chatgptrest/task_harness/evaluator_runtime.py`
  - 任务级 evaluator
  - 机器 grader + browser/API outcome grader + rubric grader
- `chatgptrest/task_harness/promotion.py`
  - promotion / reject / rollback / override
- `chatgptrest/task_harness/api.py`
  - task-centric API/operator routes

### 6.3 必须存在的一等工件

建议每个长任务都拥有一个任务工作区，至少包含：

- `TASK_REQUEST.md`
- `TASK_CONTEXT.lock.json`
- `TASK_SPEC.yaml`
- `EXECUTION_PLAN.md`
- `TASK_STATE.json`
- `CHUNK_CONTRACTS/*.json`
- `ACCEPTANCE_CHECKS.json`
- `PROGRESS_LEDGER.jsonl`
- `PROGRESS.md`
- `BUG_QUEUE.json`
- `EVALUATION_REPORTS/*.json`
- `HANDOFF.md`
- `FINAL_OUTCOME.json`
- `init.sh`
- `verify.sh`
- `tests.json`

这里最重要的新工件有四个：

1. `TASK_CONTEXT.lock`
   - 冻结本轮 planner 依赖的 authority/work-memory/context snapshot

2. `TASK_STATE`
   - 不再让任务状态散在 session / run / memory / progress note 里

3. `BUG_QUEUE`
   - evaluator 发现的问题有正式归宿

4. `FINAL_OUTCOME`
   - promoted outcome 成为上游真相，再喂给 `completion_contract`

### 6.4 状态机

建议任务级状态机至少包含：

- `intake_pending`
- `context_locked`
- `spec_ready`
- `plan_approved`
- `executing`
- `awaiting_evaluation`
- `rework_required`
- `awaiting_operator`
- `promoted`
- `published`
- `distilled`
- `archived`
- `failed`
- `canceled`

chunk 级状态建议包含：

- `draft`
- `approved`
- `in_progress`
- `delivered`
- `evaluated_pass`
- `evaluated_fail`
- `superseded`

### 6.5 两种执行模式

Task Harness 不应强制所有任务都 sprint。

应该支持：

1. `sprinted`
   - 模型边界附近的复杂长任务
   - 每个 chunk 都有 evaluator gate

2. `continuous`
   - 模型边界内的较成熟任务
   - planner 仍冻结 spec 和 acceptance
   - evaluator 在关键节点或收尾时介入

这正是从 Anthropic 新文里应吸收的“适应性 harness”。

### 6.6 durable execution 语义

这部分不应再作为附加能力，而应进入主架构。

至少要有：

- singleton concurrency per `task_id`
- checkpoint after each promoted artifact boundary
- pause / resume
- operator/human signal
- external event injection
- idempotent replay
- background run + catch-up
- attempt/chunk lineage

### 6.7 evaluator-owned promotion

任务 promotion 不应由 generator 决定，而应由 evaluator + operator 决定。

推荐关系：

- generator：写变更、写 progress、提 amendment
- evaluator：给 promote / rework verdict
- operator：approve / reject / override / rollback

当前：

- `evaluator_service` 可复用为结果 adapter
- `decision_plane` 可复用为 observer/proposal plane

但 promotion authority 需要新建。

### 6.8 task outcome 到 completion 和 memory 的单向链

建议重新冻结如下关系：

1. `FinalOutcome` 是任务结果真相源
2. `completion_contract` 从 `FinalOutcome` 派生对外交付 finality
3. `work_memory` 只接 promoted outcome 的 durable distillation

这个单向链非常关键。  
否则 memory 还会继续被误用成 task-control substitute。

---

## 7. 任务级 eval harness 应该具体补什么

### 7.1 不只是现有 tests 的包装

真正的 task-level eval harness，至少要新增：

- `task`
- `trial`
- `grader`
- `outcome`
- `evaluation suite`

这些对象在 runtime 中是显式的，而不是靠测试文件名隐式代表。

### 7.2 grader 组合

必须组合：

1. **code graders**
   - build
   - lint
   - type
   - unit / integration / e2e

2. **outcome graders**
   - browser / Playwright / CDP
   - API
   - DB / environment state

3. **rubric graders**
   - code quality
   - product depth
   - architecture adherence
   - UX / design quality

4. **human calibration**
   - operator review
   - periodic grader recalibration

### 7.3 任务级指标

后续任务级 eval harness 应追踪：

- pass@1
- pass@k
- pass^k / stability
- rerun success rate
- amendment frequency
- evaluator false-positive / false-negative
- operator override rate
- regression suite delta

### 7.4 reference solution 与真实失败集

这条后续非常重要：

- 从真实 production 失败、manual review queue、bug tracker 中抽任务
- 构造 capability suite
- 再把解决后的任务沉淀成 regression suite

---

## 8. 不该继续做什么

### 8.1 不要把下一阶段定义成“更大的 memory”

memory 仍然重要，但它已经不是当前主矛盾。

### 8.2 不要只补一个 planner

单独加 planner 不会解决：

- durable execution
- evaluator gate
- task state
- operator review

### 8.3 不要让 live retrieval 继续承担任务 scope reconstruction

这是本版明确反对的。

retrieval 应为 task bootstrap 提供输入，而不是继续作为任务定义本身。

### 8.4 不要把 completion publication 当 task truth

`completion_contract` 很重要，但它是**交付发布层**，不是任务控制层。

### 8.5 不要一开始做“大而全 swarm”

当前最该做的是：

- task object
- task workspace
- durable execution
- evaluator gate

不是先做更复杂的 swarm 编排。

---

## 9. 分阶段实施计划

### Phase 1：Task Control Plane

目标：

- 引入 `task_id / attempt_id / chunk_id`
- 建立 `TASK_STATE`
- 建立 server-authoritative task lifecycle

验收：

- 任一长任务可被 `GET /v1/tasks/{task_id}` 明确观察
- 同一 task 不会被两个 generator 并行改写

### Phase 2：Task Workspace Contract

目标：

- 从 `planning_bootstrap + context_service + task_intake` 生成
  - `TASK_CONTEXT.lock`
  - `TASK_SPEC`
  - `EXECUTION_PLAN`
  - `ACCEPTANCE_CHECKS`

验收：

- 长任务没有这些工件就不能进入 `executing`

### Phase 3：Contract-Bounded Execution

目标：

- generator 只能从 chunk contract 执行
- amendment 进入审批流

验收：

- silent scope drift 被禁止
- 每次执行都能回溯到 contract

### Phase 4：Evaluator Gate

目标：

- 落地 `BUG_QUEUE`
- 落地 `EVALUATION_REPORT`
- 落地 promote/rework 决策

验收：

- generator 不能自证通过
- evaluator verdict 成为 promotion 前置条件

### Phase 5：Task-Level Eval Harness

目标：

- capability suite
- regression suite
- reference solutions
- task/trial/grader/outcome 指标体系

验收：

- 至少有一批真实长任务能做 pass@k / stability 评估

### Phase 6：Outcome Publication & Memory Distillation

目标：

- `FinalOutcome -> completion_contract -> work_memory`

验收：

- `completion_contract` 由 promoted outcome 派生
- work-memory 只接 promoted durable conclusions

---

## 10. 最终结论

本版最终结论如下：

1. **你当前系统的核心底座方向是对的，不需要推翻。**
   - `completion_contract`
   - `canonical_answer`
   - `work_memory`
   - `planning backfill`
   - `importer/review queue`

2. **你下一阶段真正该补的，不是 memory v2，而是任务运行中枢。**

3. **这个中枢不能只叫 Task Harness Layer 就算完事。**
   它必须明确由三部分组成：
   - `Task Control Plane`
   - `Durable Execution Plane`
   - `Task-Level Eval Harness`

4. **最重要的架构重排是：**
   - 任务先被冻结
   - 执行再展开
   - evaluator 再给 promotion
   - completion 再发布
   - memory 最后蒸馏

5. **一句话总括：**

**前一阶段你已经把“回答怎么变得可信”做得很好了；下一阶段真正决定系统上限的，不再是记忆，而是把“任务怎么稳定推进到完成”也做成 first-class runtime contract。**
