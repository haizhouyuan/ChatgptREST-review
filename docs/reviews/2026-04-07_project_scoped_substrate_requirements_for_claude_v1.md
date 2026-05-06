# 2026-04-07 Project-Scoped Substrate Requirements For Claude v1

## 1. 文档目的

这份文档不是方向讨论稿，而是需求定义文档。

目标是把下面这件事说清楚：

> 如何在不重新发明一套项目专用系统的前提下，把现有 `OpenClaw / OpenMind plugins / ChatgptREST / Harness / Memory / EvoMap / Context Assembler / coding agent` 收成一个可实施、可验收、可回滚的 `project-scoped substrate`。

本稿只定义：

1. 目标
2. 边界
3. 合同
4. 字段
5. 阶段
6. 验收

本稿不执行实现。

## 2. 已核实的当前事实

以下内容是基于代码与运行时数据库确认，不是口头假设。

### 2.1 OpenClaw / plugin / ChatgptREST 关系

当前链路是：

`Feishu -> OpenClaw -> OpenMind plugin -> ChatgptREST -> execution lane`

其中：

1. `OpenClaw`
   - 前台 agent runtime
   - 当前 live front model 已切到 `MiniMax-M2.7-highspeed`

2. `OpenMind plugin`
   - 前台桥接层
   - 负责：
     - advisor 转单
     - memory recall / capture hook
     - telemetry hook
     - graph query

3. `ChatgptREST`
   - 后端状态与任务中台
   - 负责：
     - task/session/checkpoint/handoff
     - quality gate
     - execution lane routing
     - memory / evomap / context substrate

### 2.2 现有 substrate 不是假设，已经落地

#### Context / cognitive

- [context_service.py](/vol1/1000/projects/ChatgptREST/chatgptrest/cognitive/context_service.py)
- [context_assembler.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/context_assembler.py)
- [routes_cognitive.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_cognitive.py)

#### Memory / work memory

- [memory_manager.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/memory_manager.py)
- [work_memory_manager.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/work_memory_manager.py)
- [memory_capture_service.py](/vol1/1000/projects/ChatgptREST/chatgptrest/cognitive/memory_capture_service.py)

#### Event / signal / EvoMap

- [event_bus.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/event_bus.py)
- [observer.py](/vol1/1000/projects/ChatgptREST/chatgptrest/evomap/observer.py)
- [signals.py](/vol1/1000/projects/ChatgptREST/chatgptrest/evomap/signals.py)
- [retrieval.py](/vol1/1000/projects/ChatgptREST/chatgptrest/evomap/knowledge/retrieval.py)
- [schema.py](/vol1/1000/projects/ChatgptREST/chatgptrest/evomap/knowledge/schema.py)

#### OpenClaw hooks

- [openmind-memory/index.ts](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-memory/index.ts)
  - `before_agent_start`
  - `agent_end`
- [openmind-telemetry/index.ts](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-telemetry/index.ts)
  - `before_agent_start`
  - `after_tool_call`
  - `agent_end`
  - `message_sent`

### 2.3 数据库现状

运行时知识库：

- `/vol1/1000/projects/ChatgptREST/data/evomap_knowledge.db`

查到的真实数据：

1. `documents_total = 7893`
2. `distinct documents.project = 91`
3. Top `documents.project`：
   - `planning = 2942`
   - `ChatgptREST = 2222`
   - `antigravity = 1113`
   - `research = 951`

4. `atoms_total = 103874`
5. `atoms.promotion_status='active' = 202`
6. `promotion_audit_total = 505`
7. `atoms.scope_project 非空 = 26120`
8. 当前 `scope_project` 数据主要集中在 `planning`

### 2.4 已确认的关键 gap

#### Gap A：project 维度没有贯穿主热路径

已经有的：

1. `Document.project`
2. `atoms.scope_project`
3. `GraphQueryRequest.project_id`
4. `GraphService._filter_by_project(...)`

还没有贯穿的：

1. `ContextResolveRequest`
2. `ContextResolveOptions`
3. `ContextAssembler.build(...)`
4. `MemoryManager`
5. `TraceEvent / Signal`
6. OpenClaw recall/capture 主入口

#### Gap B：auto-capture 不是 authority-grade

当前 `openmind-memory` 的 auto-capture：

1. pattern-based
2. 轻量 confidence
3. session end 时截取少量候选
4. 没有 groundedness gate

因此它只能当：

1. session memory
2. weak signal
3. recall candidate

不能直接当：

1. frozen fact
2. style rule
3. project authority

#### Gap C：EvoMap 消化率低

当前更大的现实瓶颈不是“没有演化系统”，而是：

1. ingest 很多
2. active 很少
3. promotion audit 也不高

所以当前中期瓶颈是：

> 不是先扩自我进化，而是先把 project-scoped retrieval 和 promotion pipeline 真正跑起来。

## 3. 根本问题定义

当前系统的真正问题不是“缺一个项目上下文文件”，而是：

1. 人工 authority
2. 项目级工作记忆
3. 跨 session 结构化知识
4. 运行时上下文组装

这四层没有被明确区分，也没有被同一个 `project_id` 串起来。

于是系统会出现：

1. 前台入口靠 session 近邻和关键词做局部判断
2. plugin 层注入一部分项目上下文
3. backend recall 又从别的源召回一部分上下文
4. authority 内容和自动召回内容没有明确优先级
5. staged knowledge 大量存在，但 active retrieval 很弱

## 4. 目标定义

### 4.1 总目标

建设一个 `project-scoped substrate`，让所有复杂项目型请求都能在同一套底座上获得：

1. 人工 authority 优先
2. 项目级 recall
3. 跨 session continuity
4. 可审计的运行时 context packet
5. 可回放、可验证、可提权的长期演化能力

### 4.2 子目标

#### Goal 1：authority 不再被自动上下文冲掉

系统必须保证：

- 人工冻结事实
- 风格规则
- pin 住的 authority docs

在任意情况下都优先于自动 recall / 自动知识。

#### Goal 2：project scope 进入 recall 主链

系统必须保证：

- 不同项目下，同样 query 的 recall 结果不同
- recall 不再主要依赖 session/thread 近邻
- recall 能按项目聚焦

#### Goal 3：项目记忆、项目知识、运行时上下文被明确分层

系统必须明确区分：

1. authority anchor
2. project memory
3. knowledge base
4. runtime context

#### Goal 4：Harness 后续可以基于 project-scope 做回放和提权

系统必须为后续 Harness 留出可操作接口：

- project_id
- context source breakdown
- authority hit evidence
- project-scoped retrieval traces

## 5. 非目标

本项目明确不做：

1. 不新建 project-specific agent/workspace topology
2. 不让 plugin 变成新的项目主脑
3. 不把 `_project_context.md` 扩成动态大缓存
4. 不现在就实现完全自动化的 self-evolution
5. 不为了当前两个 planning 项目做只适用于 planning 的专用 schema

## 6. 分层模型

最终必须同时存在 5 层，不是替代关系。

### Layer 1：Authority Anchor

载体：

- `_project_context.md`

职责：

1. `frozen_facts`
2. `style_rules`
3. `pinned_authority_docs`
4. 人工阶段定调

原则：

1. 只允许人改
2. 不自动覆盖
3. 不承担动态缓存职责

### Layer 2：Project Memory

载体：

- `MemoryManager`
- `WorkMemoryManager`
- project-scoped work memory objects

职责：

1. 当前 open loops
2. current branch
3. next actions
4. continue/branch 线索
5. 项目级 active context

原则：

1. 允许系统自动写入
2. 允许人工修正
3. 不等于 authority truth

### Layer 3：Knowledge Base

载体：

- `EvoMap`

职责：

1. 跨 session 结构化知识
2. 可 promotion 的 decision / procedure / lesson 等 atoms
3. project-scoped knowledge retrieval

原则：

1. 允许系统自动 ingest
2. 通过 promotion pipeline 激活
3. 不能覆盖 authority anchor

### Layer 4：Runtime Context

载体：

- `ContextResolver`
- `ContextAssembler`
- prompt assembly chain

职责：

1. 每次请求动态组装 context packet
2. 根据优先级和 token budget 裁剪
3. 产出可审计的 source/provenance breakdown

### Layer 5：Harness

载体：

- eval / replay / acceptance / regression 工具链

职责：

1. 回放项目任务
2. 检查 authority 是否命中
3. 检查 project-scoped retrieval 是否命中
4. 检查 output 是否遵守 project rules

## 7. 权限与优先级合同

这是本需求最关键的合同。

### 7.1 优先级顺序

运行时上下文的优先级必须固定为：

1. `Authority anchor`
2. `Project memory`
3. `EvoMap knowledge`
4. `KB evidence`
5. `Runtime heuristics / generic recall`

说明：

1. `authority anchor` 永远最高
2. `KB evidence` 当前不 project-scoped，排在 `EvoMap knowledge` 之后
3. session/thread 近邻只能当弱线索，不能覆盖 authority

### 7.2 注入点合同

优先级合同不能只在 `ContextAssembler` 里成立，必须同时覆盖两个注入点。

#### 注入点 A：ContextAssembler / ContextResolver

要求：

1. `project-scoped` memory / knowledge retrieval 顺序必须显式固定
2. 输出必须附带 source breakdown

#### 注入点 B：Prompt Builder 最终拼装

当前实际情况：

- [prompt_builder.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/prompt_builder.py)
  中 `{available_inputs}` 被直接插进最终 user prompt
- `openmind-advisor` 现在通过 `task_intake.available_inputs.project_context` 注入 authority anchor

因此要求：

1. `available_inputs.project_context` 对应的 authority 内容必须排在 runtime assembled context 之前
2. token 裁剪不能先裁 authority anchor
3. prompt 里必须能清楚区分：
   - authority
   - project memory
   - project knowledge
   - generic evidence

## 8. 详细功能需求

### FR-1：Authority anchor 收紧

系统必须支持每个项目一个 `_project_context.md`，且该文件只允许包含：

1. `frozen_facts`
2. `style_rules`
3. `pinned_authority_docs`
4. `phase_positioning`
5. `project_aliases`

不允许继续把以下内容塞进去：

1. 自动扫描出的最新文件摘要
2. 动态 runtime state
3. 大段项目过程缓存

验收：

1. 任一项目 authority anchor 文件长度可控
2. 内容可由人直接校对
3. 没有显著动态缓存内容

### FR-2：MemoryManager 增加 `project_id`

系统必须为 `memory_records` 增加 `project_id` 一等字段。

要求：

1. schema migration 自动补列
2. 新写入支持 `project_id`
3. 读取支持 `project_id`
4. dedup / query / audit 路径都能带 `project_id`

验收：

1. `get_episodic()` 支持按 `project_id` 过滤
2. `get_semantic()` 支持按 `project_id` 过滤
3. 写入 audit trail 时可看到 project 归属

### FR-3：Context resolve 增加 `project_id`

系统必须把项目维度带进 context resolve 主链。

涉及：

1. [routes_cognitive.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_cognitive.py)
   - `ContextResolveRequest`
2. [context_service.py](/vol1/1000/projects/ChatgptREST/chatgptrest/cognitive/context_service.py)
   - `ContextResolveOptions`
3. [context_assembler.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/context_assembler.py)
   - `build(...)`

验收：

1. `/v2/context/resolve` 接口可显式传 `project_id`
2. 返回结果显示 project-scoped retrieval 已生效

### FR-4：EvoMap retrieval 真正使用项目维度

系统必须让主 retrieval 路径而不只是 graph query 路径吃到 project scope。

涉及：

1. [retrieval.py](/vol1/1000/projects/ChatgptREST/chatgptrest/evomap/knowledge/retrieval.py)
2. [schema.py](/vol1/1000/projects/ChatgptREST/chatgptrest/evomap/knowledge/schema.py)

硬要求：

1. `Atom` dataclass 必须补 `scope_project`
2. retrieval 支持按 `scope_project` 过滤
3. retrieval 没有 `scope_project` 时才回退到 document project / generic retrieval

验收：

1. `Atom.from_row()` 不再静默丢弃 `scope_project`
2. retrieval 结果可按 `project_id` 显著收窄

### FR-5：Signal / telemetry 增加项目维度

系统必须让：

1. `TraceEvent`
2. `Signal`
3. telemetry ingest
4. OpenClaw telemetry plugin

都支持 `project_id`。

目的：

1. 后续可按项目看行为漂移
2. Harness 可按项目做 replay / comparison

验收：

1. 同一项目的事件可聚合
2. 不同项目可分开看 signal 分布

### FR-6：OpenClaw 入口 project association

系统必须让 OpenClaw 在命中已知项目时稳定携带项目信息。

要求：

1. 继续保留 `projectRef -> project_id` 映射
2. 规则优先，模型补充
3. 不依赖模型自由推理决定 authority docs

验收：

1. 命中项目关键词时，进入 advisor 的请求带 `projectRef / project_id`
2. backend 可见 project-scoped task intake

### FR-7：project-scoped work memory objects

系统必须把以下对象收成通用 project memory，不允许做 planning-only schema：

1. `active_project`
2. `decision_ledger`
3. `handoff`
4. `post_call_triage`
5. `open_loops`
6. `next_actions`

要求：

1. schema 必须是通用结构
2. 不允许写成只适用于某一项目或某一业务域的固定字段组合

验收：

1. 任意项目都能复用同一 object shape
2. 不需要为每个项目定义新 schema

### FR-8：Harness 支持 project-scoped replay

在 Phase 6 前，系统必须已经具备可供 Harness 使用的最小字段：

1. `project_id`
2. context source breakdown
3. authority hit evidence
4. retrieval source counts

验收：

1. 同一任务 replay 时可以对比 project-scoped context 是否命中
2. 可以判断本轮输出是否真的用了 authority anchor

## 9. 非功能性需求

### NFR-1：不新增 project-specific topology

禁止：

1. 新增每个项目一个 agent workspace
2. 新增每个项目一套 plugin 配置
3. 新增每个项目一套 prompt builder

### NFR-2：authority 必须人工可控

任何自动化系统都不得自动覆盖：

1. `frozen_facts`
2. `style_rules`
3. `pinned_authority_docs`

### NFR-3：project memory schema 必须通用

不得引入只服务于某个项目的 object schema。

### NFR-4：必须可审计

运行时至少能回答：

1. 这次 authority anchor 注入了什么
2. 这次 project memory 注入了什么
3. 这次 EvoMap knowledge 注入了什么
4. 哪一层最终影响了 prompt

## 10. 实施阶段

### Phase 0：Authority anchor 收紧

产出：

1. authority anchor 内容边界冻结
2. 现有 `_project_context.md` 收紧

退出条件：

1. `_project_context.md` 不再承担动态缓存职责

### Phase 1 + Phase 2：同一 sprint 并行完成

> 注意：这两阶段不能串行，必须同步做。

#### Phase 1

1. `project_id` 贯穿：
   - memory
   - context resolve
   - context assembler
   - telemetry/signal
   - advisor/plugin ingress

2. `Atom.scope_project` dataclass 修复

3. `ContextResolveRequest` 补 `project_id`

#### Phase 2

1. authority 优先级合同落地
2. 同时覆盖：
   - `ContextAssembler`
   - `prompt_builder`

退出条件：

1. project-scoped retrieval 已工作
2. authority 永远高于自动 recall

### Phase 3：入口 project association 稳定化

产出：

1. OpenClaw 项目识别更稳
2. advisor 转单稳定带 `projectRef/project_id`

退出条件：

1. Feishu 项目请求稳定进入 advisor 主链

### Phase 4：project memory 对象化

产出：

1. open loops / next actions / current branch 成为通用项目级 work memory 对象

退出条件：

1. continue/branch 项目记忆明显更稳

### Phase 5：promotion pipeline 恢复

产出：

1. 确认 staged 长期堆积根因
2. 批量 promotion 或 gate 调整方案

退出条件：

1. active knowledge 占比显著提升

### Phase 6：Harness 驱动回放与提权

产出：

1. project-scoped replay
2. authority hit validation
3. retrieval effectiveness comparison

退出条件：

1. 同一项目经过回放可观察到命中率和遵规率提升

## 11. 验收矩阵

### A. 数据层验收

1. `memory_records` 有 `project_id`
2. `TraceEvent` 有 `project_id`
3. `Signal` 有 `project_id`
4. `Atom` dataclass 有 `scope_project`

### B. recall 层验收

1. `/v2/context/resolve` 可传 `project_id`
2. 同 query 在不同 `project_id` 下结果不同
3. authority anchor 明显排在其他 source 之前

### C. prompt 层验收

1. `prompt_builder` 最终 prompt 中 authority section 先于 runtime recall
2. token 裁剪不先裁 authority anchor

### D. OpenClaw 入口验收

1. Feishu 发项目型消息时，OpenClaw 能稳定带 `projectRef/project_id`
2. 不再出现前台自己乱找文件而不转单

### E. project memory 验收

1. 跨 session 仍能 recall 项目 open loops
2. continue/branch 使用同一项目记忆对象

### F. promotion 验收

1. active atom 数量提升
2. project-scoped retrieval 中 active atoms 占比提升

## 12. 回滚边界

如果任一阶段上线后出现：

1. authority 被自动检索覆盖
2. recall 范围异常扩大
3. OpenClaw 项目识别误触发激增
4. project memory 污染严重

必须允许：

1. 回退 project-scoped retrieval
2. 回退 prompt ordering
3. 关闭 project-scoped recall
4. 保留 authority anchor 继续作为最低保障

## 13. 给 Claude 的审核问题

请重点审这 8 条：

1. `project_id` 贯穿主链的定义是否完整
2. `Atom.scope_project` 修复是否应列为 Phase 1 前置阻断
3. authority 优先级合同是否覆盖了所有注入点
4. `KB evidence` 归入 runtime heuristics 的定位是否合理
5. Phase 1 与 Phase 2 并行的要求是否必要
6. Phase 4 的通用 project memory schema 约束是否足够避免补丁系统
7. Phase 5 是否还缺更明确的 promotion 恢复动作
8. 这份需求定义是否已经足够细，能直接指导后续设计与实施

## 14. 最终判断

一句话总结：

> 当前应该做的，不是继续扩一个项目专用配置系统，而是保留一个永久的人类 authority anchor，并把现有 `Harness / Memory / EvoMap / Context Assembler` 真正 project-scope 化，再用明确的优先级合同把它们收成一个平台级 substrate。
