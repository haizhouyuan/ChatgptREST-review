# 2026-04-02 Planning Unified Logical Task Layer v1

## 1. 目的

这份文档只回答一个问题：

> 当 `planning/` 第一阶段允许多端使用时，怎样避免“窗口越来越多、记忆越来越乱、任务线程越来越散”。

这里先不谈完整实现蓝图，只先冻结一版 **统一逻辑任务层** 的定义。

它要解决的不是：

1. 选飞书还是选 TUI
2. 选 Codex 还是选 Claude Code
3. 选 ChatGPT 还是 Gemini

它真正要解决的是：

1. 同一件工作如何跨入口连续推进
2. 什么是真正的任务真相源
3. 什么该进入长期记忆，什么只属于当前窗口
4. 什么时候算“继续旧任务”，什么时候必须开新任务

## 2. 当前问题复述

结合前面的 surface matrix、lane matrix、以及当前实际使用方式，问题已经很明确：

1. 你现在真正的主工作台是 `Codex / Claude Code / Antigravity`
2. `tmuxagent(8702)` 是这些工作台的远程入口和控制面
3. `Feishu / OpenClawBot` 有成为统一入口的潜力，但当前效果还达不到替代深度 workbench 的程度
4. 真正让人乱的，不是入口多，而是 **任务线程、会话线程、记忆线程没有被明确分层**

如果不先定义这层，后面无论：

1. 把更多任务发到飞书
2. 继续在多个 TUI/IDE 里推进
3. 引入更强的 harness / evaluator / review

都会继续积累认知负担。

## 3. 核心结论

### 3.1 不要强求单一界面，要强求单一逻辑任务层

第一阶段最稳的方向不是：

- “只有一个窗口”
- “所有任务都只能从一个入口发”

而是：

- **允许多端**
- **统一任务真相源**
- **统一 checkpoint**
- **统一记忆分层**

### 3.2 窗口是临时容器，任务线程才是长期对象

对 `planning/` 第一阶段，应该冻结下面这句：

> 飞书、Codex、Claude Code、Antigravity、tmuxagent 都只是进入同一逻辑任务层的不同 surface；真正持续存在的不是窗口，而是 `task_id + checkpoint + memory scope`。

### 3.3 session truth 不能等于 task truth

当前仓里已经有几种不同的“连续性对象”：

1. `state/agent_sessions/*`
   - 这是 public agent facade 的 session truth
2. `task_runtime.tasks.task_id`
   - 这是 task runtime 的 task truth
3. `task_runtime.tasks.logical_task_key`
   - 这是 task 与上游逻辑键的连接点
4. `task_intake_spec_v2.task_id`
   - 这是上游 caller 传入稳定任务标识的预留位

所以第一阶段不该再把“session 连续性”误当成“任务连续性”。

正确口径应是：

- `session_id` 负责会话恢复
- `task_id` 负责工作线程连续性
- `checkpoint` 负责跨端 handoff
- `memory scope` 负责哪些信息进入哪一层记忆

## 4. 代码现实

## 4.1 仓里已经有 `task_id` 的基座

[task intake spec v2](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-21_task_intake_spec_v2.json#L17) 已经给了可选的 `task_id`：

- “Optional stable task identifier allocated by upstream caller or runtime.”

[TaskInitializer.initialize_task()](/vol1/1000/projects/ChatgptREST/chatgptrest/task_runtime/task_initializer.py#L61) 会把 `intake_spec.task_id` 落到 task runtime 的 `logical_task_key`：

- `logical_task_key=intake_spec.task_id`

[task store schema](/vol1/1000/projects/ChatgptREST/chatgptrest/task_runtime/task_store.py#L190) 也已经显式有：

- `task_id`
- `logical_task_key`
- `intake_json`
- `context_lock_json`

这说明“稳定任务线程”这个方向不是凭空想象，而是 repo 里已经有基座，只是还没成为 planning 第一阶段的统一治理对象。

## 4.2 仓里已经有 checkpoint / state 语义

[task runtime api routes](/vol1/1000/projects/ChatgptREST/chatgptrest/task_runtime/api_routes.py#L29) 已经暴露：

1. `POST /v1/tasks`
2. `GET /v1/tasks/{task_id}`
3. `POST /v1/tasks/{task_id}/resume`
4. `POST /v1/tasks/{task_id}/signals`
5. `POST /v1/tasks/{task_id}/operator/*`

[task state schema](/vol1/1000/projects/ChatgptREST/chatgptrest/task_runtime/task_store.py#L106) 也已经持久化：

- `phase`
- `status`
- `last_checkpoint_at`
- `awaiting_signal`
- `blocked_reason`
- `state_data_json`

所以第一阶段并不是从零开始发明 “checkpoint/resume”，而是要把这些现有能力翻译成适合 `planning` 工作的统一规则。

## 4.3 仓里已经有 session 层，但那不是 planning 的最终真相源

[AgentSessionStore](/vol1/1000/projects/ChatgptREST/chatgptrest/api/agent_session_store.py#L10) 负责的是：

- `state/agent_sessions/<session_id>.json`
- `state/agent_sessions/<session_id>.events.jsonl`

它适合：

1. public agent facade 的持续会话
2. SSE 事件恢复
3. 同一个 session 内的后续轮次

它不适合直接承担：

1. planning 长任务的多周连续性
2. 多入口共用同一任务线程
3. 任务级记忆分层

这也是为什么第一阶段必须把 `session_id` 和 `task_id` 分开。

## 5. 统一逻辑任务层的 4 个冻结定义

## 5.1 `task_id`

### 定义

`task_id` 是一个 **稳定的工作线程标识**，表示“同一件 planning 工作”。

它不等于：

1. 飞书 thread
2. MCP session
3. TUI 窗口
4. tmux pane

它也不应该被理解成：

- “某一次调用的 run id”
- “某一个界面的 session id”

### 对 `planning/` 的正确语义

一个 `task_id` 应该对应：

1. 一个明确目标
2. 一个明确对象
3. 一个明确输出方向
4. 一条持续推进的工作线程

例如：

1. “北美镁合金结构件项目阶段诊断与下一步推进建议”
2. “2026 年度人员规划方案”
3. “某次会议录音到行动项和记忆变更建议”

### 设计原则

1. `task_id` 允许跨多次会话延续
2. `task_id` 允许跨多种 surface 延续
3. `task_id` 不应因为换了终端、换了入口、换了模型就变化
4. `task_id` 之下可以有多个短期 session

## 5.2 `checkpoint`

### 定义

`checkpoint` 是某个 `task_id` 的 **跨端 handoff 工件**。

它的作用不是存所有聊天记录，而是回答：

1. 现在做到哪了
2. 什么已经确认
3. 什么还没确认
4. 下一步该怎么接着做

### 第一阶段最小字段

每个 checkpoint 至少应包含：

1. `task_id`
2. `task_title`
3. `project_or_topic_ref`
4. `current_objective`
5. `current_output_target`
6. `current_status`
7. `confirmed_scope`
8. `open_questions`
9. `current_artifact_refs`
10. `decision_summary`
11. `next_actions`
12. `memory_writeback_candidates`
13. `last_updated_at`
14. `last_surface`

### 正确用途

1. 飞书里发起的新任务，可以先生成一个初始 checkpoint
2. 深度工作台推进一轮后，必须写回 checkpoint
3. 手机、飞书、TUI、IDE 再次接手时，不靠翻旧窗口，而靠读 checkpoint

### 不该承载的东西

checkpoint 不应该变成：

1. 全量聊天 transcript
2. 全量长期记忆库
3. 所有中间草稿的堆积场

它应该是 **handoff artifact**，不是垃圾堆。

## 5.3 `memory scope`

### 定义

`memory scope` 用来回答：

> 这条信息应该只留在当前窗口，还是应该成为任务记忆、项目记忆，甚至变成 planning 的长期稳定真相。

### 第一阶段建议冻结 4 层

#### L0. Session Scratch

只属于当前窗口或当前短轮次。

典型内容：

1. 临时讨论
2. 尚未确认的猜测
3. 一次性中间推演
4. 草稿式口头指令

规则：

- 默认可丢弃
- 不自动写入长期记忆

#### L1. Task Working Memory

属于某个 `task_id` 的工作线程记忆。

典型内容：

1. 当前目标
2. 已确认的边界
3. 当前输出形态
4. 已完成步骤
5. 未解决问题
6. 当前阶段结论

规则：

- 跟着 `task_id` 走
- 可跨端恢复
- 任务完结后可归档，不直接等于长期项目事实

#### L2. Project / Topic Durable Memory

属于项目、专题、研究主题的稳定记忆。

典型内容：

1. 项目阶段
2. 下一里程碑
3. 主风险
4. 负责人
5. 唯一口径入口
6. 稳定结论与证据入口

规则：

- 只有经过确认的稳定信息才能升格到这一层
- 这一层应能回指 `planning/` 内的真实入口与台账

#### L3. Governance / EvoMap Memory

属于方法和能力改进层。

典型内容：

1. 哪类任务容易理解偏
2. 哪类入口最容易命中旧稿
3. 哪类 checkpoint 字段总是不够
4. 哪类验收常失败

规则：

- 这层不服务当前任务本身
- 它服务后续系统改进与复盘

### 最重要的纪律

1. 未确认事实不能直接升格到 L2
2. 临时猜测不能自动升格到 L2/L3
3. L1 可以跨端连续，但不等于永久保留一切
4. 进入 L2/L3 的内容必须带证据和入口回指

## 5.4 “新任务” vs “继续任务”

### 继续任务

满足下面大多数条件时，应默认判定为 **继续旧任务**：

1. 目标还是同一件事
2. 作用对象还是同一项目/主题
3. 输出方向还是同一主交付物
4. 这轮只是补材料、继续迭代、进一步澄清、下一步推进
5. 当前工作仍能接在已有 checkpoint 后面

例如：

1. “把昨天的项目诊断稿继续改成董事长版”
2. “补充这场会议录音，再更新行动项”
3. “在原研究结论稿基础上加一页竞争对手比较”

### 新任务

满足下面任一高权重条件时，应默认开 **新任务**：

1. 目标已经变了
2. 输出对象已经变了
3. 交付物类型已经变了
4. 原任务已经完成，这轮是全新工作
5. 原有 checkpoint 已无法承接新的工作意图

例如：

1. 从“会议纪要”转成“年度组织规划方案”
2. 从“内部工作稿”转成“客户对外报价方案”
3. 从“研究稿”转成“项目落地执行方案”

### 推荐补一条中间态

第一阶段最好额外承认一个状态：

- `branch_from_existing_task`

它表示：

1. 与旧任务强相关
2. 但这轮目标明显扩大或分叉
3. 应新开 `task_id`
4. 但需要回链到 parent task

这样可以避免两种极端：

1. 什么都塞进一个旧任务，最后线程越来越乱
2. 稍微改一下就全开新任务，丢失上下文连续性

## 6. 推荐工作模型

## 6.1 统一入口，不等于唯一工作台

第一阶段最稳的模型是：

1. `Feishu / OpenClawBot`
   - 统一收件箱
   - 发起新任务
   - 继续旧任务
   - 扔材料
   - 看状态
2. `Codex / Claude Code / Antigravity`
   - 深度执行
   - 读写仓库
   - 长轮次推进
   - 高质量成稿
3. `tmuxagent(8702)`
   - 远程继续已有 workbench

真正要统一的是：

1. `task_id`
2. checkpoint
3. memory scope
4. 新任务/继续任务判断

### 6.2 用户视角的正确体验

用户最理想的体验不是：

- “我得记住哪个窗口还开着”
- “我得记住这条消息到底该发到哪个 pane”

而是：

1. 我发一个任务
2. 系统判断这是新任务还是继续旧任务
3. 系统分配或绑定 `task_id`
4. 轻任务可在飞书完成
5. 深任务升级到深度工作台
6. 任一端回来都能恢复到上一个 checkpoint

## 7. 第一阶段最该冻结的 5 条规则

1. **`task_id` 是 planning 工作线程真相源，不是窗口真相源。**
2. **`session_id` 只负责会话连续，不负责任务连续。**
3. **任一 surface 的阶段性完成，都必须写回 checkpoint。**
4. **长期记忆必须分层，未确认事实不得升格。**
5. **“继续旧任务”是默认优先，但当目标/对象/交付物明显改变时必须开新任务或 branch。**

## 8. 对后续实现的启发

这份文档先冻结的是治理定义，不是完整实现。

但它已经清楚给出后续实现方向：

1. 上游入口必须能分配或识别 `task_id`
2. 飞书入口必须能做 `new / continue / branch` 判断
3. 深度工作台必须有“写回 checkpoint”的稳定动作
4. 记忆写回必须区分 L0/L1/L2/L3
5. 后续 harness/evaluator/EvoMap 都应围绕 `task_id` 运转，而不是围绕某个窗口运转

## 9. 一句话结论

对 `planning/` 第一阶段，最值得冻结的不是“唯一入口”，而是：

> 用 `task_id + checkpoint + memory scope + 新任务/继续任务规则` 组成一个统一逻辑任务层；飞书、Codex、Claude Code、Antigravity、tmuxagent 都只是进入这层的不同 surface。
