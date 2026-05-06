# 2026-04-07 Project-Scoped Substrate Adoption Plan For Claude v1

## 1. 这份文档要回答什么

本轮讨论已经从“planning 两个项目怎么接住”扩展到了更大的平台问题：

1. 现有 `Harness / Memory / EvoMap / Context Assembler` 这些基础设施还值不值得继续建设
2. 项目上下文到底应不应该继续靠 `_project_context.md`
3. “自我进化”到底是现在就该推主线，还是还早
4. 现有系统里哪些能力已经有了，哪些还只是概念

这份文档不是再设计一套新系统，而是基于当前真实代码和真实数据库状态，给出一条可实施的 adoption plan。

结论先行：

> 正路不是继续扩一个项目专用静态上下文系统，而是保留一个永久的人类 authority anchor，并把现有 `Memory / EvoMap / Context Assembler / Harness` 真正 project-scope 化。

## 2. 这次调研确认的事实

### 2.1 现有 substrate 不是概念，已经真实存在

以下能力都已经在代码里落地：

1. 多源上下文组装与 token 预算
   - [context_service.py](/vol1/1000/projects/ChatgptREST/chatgptrest/cognitive/context_service.py)
   - [context_assembler.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/context_assembler.py)

2. 四层记忆与工作记忆治理
   - [memory_manager.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/memory_manager.py)
   - [work_memory_manager.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/work_memory_manager.py)
   - [memory_capture_service.py](/vol1/1000/projects/ChatgptREST/chatgptrest/cognitive/memory_capture_service.py)

3. OpenClaw 侧 recall/capture hooks
   - [openmind-memory/index.ts](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-memory/index.ts)
   - `before_agent_start`
   - `agent_end`

4. 事件/信号/EvoMap 观察层
   - [event_bus.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/event_bus.py)
   - [observer.py](/vol1/1000/projects/ChatgptREST/chatgptrest/evomap/observer.py)
   - [signals.py](/vol1/1000/projects/ChatgptREST/chatgptrest/evomap/signals.py)
   - [routes_evomap.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_evomap.py)

### 2.2 项目维度不是从零开始缺失

代码层已经有 project 相关字段和局部能力：

1. EvoMap 知识层
   - [schema.py](/vol1/1000/projects/ChatgptREST/chatgptrest/evomap/knowledge/schema.py) 中 `Document.project`
   - 同一文件中 `Atom` 还有 `scope_project`

2. Graph retrieval 已支持项目过滤
   - [graph_service.py](/vol1/1000/projects/ChatgptREST/chatgptrest/cognitive/graph_service.py)
   - `_query_personal_graph(..., project_id=...)`
   - `_filter_by_project(...)`

3. Cognitive API 已经有部分 project 参数
   - [routes_cognitive.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_cognitive.py)
   - `GraphQueryRequest.project_id`
   - `KnowledgeIngestItemRequest.project_id`

### 2.3 但主热路径还没真正吃上 project scope

主 recall / runtime context 这一条线还没有真正 project-scoped：

1. [context_service.py](/vol1/1000/projects/ChatgptREST/chatgptrest/cognitive/context_service.py)
   - `ContextResolveOptions` 里没有 `project_id`

2. [routes_cognitive.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_cognitive.py)
   - `ContextResolveRequest` 里没有 `project_id`

3. [context_assembler.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/context_assembler.py)
   - `build(...)` 没有 `project_id`
   - 当前主要还是 `session + query + tier` 组合

4. [memory_manager.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/memory_manager.py)
   - 现在成熟的 scoping 是：
     - `session_id`
     - `agent_id`
     - `role_id`
     - `account_id`
     - `thread_id`
   - 还没有 `project_id`

### 2.4 数据库现状确认

本次直接查了运行时知识库：

- 运行库路径：
  - `/vol1/1000/projects/ChatgptREST/data/evomap_knowledge.db`

查到的真实数据：

1. `documents_total = 7893`
2. `distinct document.project = 91`
3. Top projects:
   - `planning = 2942`
   - `ChatgptREST = 2222`
   - `antigravity = 1113`
   - `research = 951`

4. `atoms_total = 103874`
5. `promotion_status='active' = 202`
6. `promotion_audit_total = 505`
7. `atoms.scope_project 非空 = 26120`
8. 当前 `scope_project` 基本集中在 `planning`

因此：

> Claude 的关键判断成立：project-related schema 和数据都不是空白，真正缺的是“主 recall / retrieval / runtime context 没把它吃进主链”。

### 2.5 auto-capture 现在确实不是 authority-grade

`openmind-memory` 插件已经是真挂在 OpenClaw 上，但当前定位仍是轻量记忆：

- [openmind-memory/index.ts](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-memory/index.ts)
- `autoRecall` 在 `before_agent_start`
- `autoCapture` 在 `agent_end`

它的当前性质：

1. 更像 session note / recall hint
2. 适合弱信号记忆
3. 不适合 authority truth

所以：

> 不能把 auto-capture 直接升格成项目冻结事实或长期口径源。

## 3. 采纳 Claude 的哪些判断

本轮采纳 Claude 的核心判断如下：

1. `_project_context.md` 不该被当成“临时缓存”
   - 它应该保留为长期存在的人类 authority anchor

2. `project scope` 不是一个大战略 phase
   - 更像是现有 substrate 的 threading 工作

3. 当前不该把重点放在“自我进化宣传”
   - 因为 promotion / 消化链当前吞吐明显不够

4. 最终形态不是替代链，而是分层共存
   - authority anchor
   - project memory
   - knowledge base
   - runtime context

## 4. 我的独立判断

我在采纳 Claude 主判断的同时，补两条自己的硬约束。

### 4.1 `_project_context.md` 必须收紧角色

它不该继续做：

1. 自动汇总“最近项目状态”
2. 动态缓存 authority docs 列表
3. 充当大而全的项目摘要仓库

它应该只做：

1. `frozen_facts`
2. `style_rules`
3. 人工 pin 的 authority 口径
4. 当前阶段的人工定调

一句话：

> `_project_context.md` 不是项目缓存，而是 authority anchor。

### 4.2 必须先写死上下文优先级合同

在 dynamic assembly 真正开始之前，必须明确写死：

1. authority anchor
2. project-scoped work memory
3. project-scoped EvoMap knowledge
4. runtime heuristics

谁高谁低不能靠实现细节去“自然形成”，必须是显式合同。

否则后面一定会出现：

- 自动检索结果覆盖人工冻结事实
- style rules 被普通 recall 冲掉
- session 近邻比 authority anchor 更强

## 5. 最终目标架构

最终要同时存在 5 层，而不是谁替代谁：

### Layer 1：Authority Anchor

来源：

- `_project_context.md`

内容：

- 人工冻结事实
- 写作规则
- pin 住的 authority 口径
- 当前阶段的人工定调

谁能改：

- 只有人

### Layer 2：Project Memory

来源：

- `MemoryManager + WorkMemoryManager + project_id`

内容：

- 项目级工作记忆
- continue/branch 线索
- 当前 open loops
- 已经确认但还不值得进 authority anchor 的项目状态

谁能改：

- 系统自动写入
- 人工修正

### Layer 3：Knowledge Base

来源：

- `EvoMap + project scope`

内容：

- 跨 session 的结构化项目知识
- 可 promotion 的决策/经验/过程原子

谁能改：

- ingest + promotion pipeline

### Layer 4：Runtime Context

来源：

- `ContextResolver + ContextAssembler`

内容：

- 每次请求动态组装的上下文包
- 根据 token budget 和优先级进行裁剪

### Layer 5：Harness

来源：

- eval / acceptance / replay / regression

内容：

- 回放真实任务
- 比较不同版本行为
- 验证 project rules 是否真被命中
- 为 future tuning 提供证据

## 6. 分阶段可实施方案

### Phase 0：收紧 authority anchor

目标：

- 让 `_project_context.md` 只承担人工 authority 职责

动作：

1. 保留现有 `_project_context.md`
2. 删除或迁出其中会动态过期的“自动状态摘要”
3. 只保留：
   - `frozen_facts`
   - `style_rules`
   - pin 住的 authority 口径
   - 人工阶段定调

验收：

1. 文件长度明显收缩
2. 内容以“人类判断”为主，而不是“动态缓存”为主
3. 不再尝试维护一长串容易过期的运行时状态

### Phase 1：把 `project_id` 贯穿 substrate 主链

目标：

- 让项目维度进入 memory / context / signals 主线

范围：

1. [memory_manager.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/memory_manager.py)
2. [work_memory_manager.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/work_memory_manager.py)
3. [context_service.py](/vol1/1000/projects/ChatgptREST/chatgptrest/cognitive/context_service.py)
4. [context_assembler.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/context_assembler.py)
5. [routes_cognitive.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_cognitive.py)
6. [event_bus.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/event_bus.py)
7. [signals.py](/vol1/1000/projects/ChatgptREST/chatgptrest/evomap/signals.py)
8. `openmind-memory / openmind-telemetry / openmind-advisor` 插件入口

动作：

1. 给 memory records 增加 `project_id`
2. 给 context resolve 增加 `project_id`
3. 给 telemetry / signal / trace 增加 `project_id`
4. 让 `projectRef` 稳定映射到 `project_id`

验收：

1. 同一查询在不同 `project_id` 下 recall 结果不同
2. memory recall 不再只依赖 session/thread
3. trace 与 telemetry 可以按项目聚合

### Phase 2：写死上下文优先级合同

目标：

- 防止 dynamic assembly 把人工 authority 冲掉

优先级必须固定为：

1. `_project_context.md` 中的人类 authority
2. project-scoped work memory
3. project-scoped EvoMap knowledge
4. runtime heuristics

动作：

1. 在 `ContextResolver` 里显式加入 authority block
2. 在 `ContextAssembler` 中显式保证先后顺序
3. 输出 provenance / source breakdown，便于诊断

验收：

1. 当自动召回结果与 authority anchor 冲突时，authority 永远赢
2. runtime context 里能清楚看到每块上下文来自哪一层

### Phase 3：让 OpenClaw 厚在“项目关联与编排”

目标：

- 前台入口更稳，但不把复杂项目脑子塞进去

前提：

- 前台当前已切到 `MiniMax-M2.7-highspeed`
- 但入口增强仍然坚持“规则优先，模型补充”

动作：

1. 保留高信号词项目路由
2. 把 `projectRef -> project_id` 固化
3. continue/branch/status 优先走保守规则，不走自由猜测
4. `openmind-advisor` 只做桥，不继续积累业务脑子

验收：

1. Feishu 里的项目型话术能稳定进入 advisor 主链
2. 不再出现前台自己乱找文件而不转单的情况

### Phase 4：把 project-scoped work memory 真正用起来

目标：

- 项目级工作记忆能够跨 session 为 continue/branch 提供支撑

动作：

1. 建立项目级 active context 对象
2. 让 continue/branch/checkpoint 与 project memory 对齐
3. 把 open loops / next actions / current branch 变成明确对象

验收：

1. 换 session 仍能按项目召回 open loops
2. continue 的上下文明显更稳
3. 项目内多个线程不再彼此完全失忆

### Phase 5：修 promotion pipeline，再谈演化

目标：

- 提高“消化率”，而不是继续堆 staged atoms

现状：

1. `103874` atoms
2. 只有 `202` active
3. `promotion_audit = 505`

说明：

- 问题不在 ingest
- 问题在 promotion / groundedness / activation 没跑起来

动作：

1. 分析 staged 无法进入 active 的主原因
2. 优先提升 project-critical atoms 的 promotion 吞吐
3. 不急着做复杂 actuator 自动调参

验收：

1. active atoms 占比显著提升
2. 至少在 `planning` 项目域，关键规则和决策能进入 active retrieval

### Phase 6：最后才做 Harness 驱动的自我改进

目标：

- 让系统通过真实任务回放和反馈变好

前提：

1. `project_id` 已贯穿主链
2. authority 优先级已固定
3. promotion pipeline 已经不再近乎停滞

Harness 在这里负责：

1. 回放真实项目任务
2. 比较不同版本是否命中了正确项目上下文
3. 比较输出是否遵守 authority rules
4. 为 future 提权 / 退权提供证据

验收：

1. 项目规则命中率随版本演进提高
2. 重复纠正的 style/fact 规则能够稳定前置
3. 新项目不需要重新发明一套上下文系统

## 7. 明确不建议的路线

### 7.1 不建议继续把 `_project_context.md` 做成大而全项目缓存

原因：

1. 一定会过期
2. 人工维护负担过大
3. 和已有 substrate 重复

### 7.2 不建议现在把重点放在“自我进化很强大”

原因：

1. 当前 promotion 消化率太低
2. 先让 recall / retrieval / activation 真跑起来更重要

### 7.3 不建议把 OpenMind plugin 再变厚

原因：

1. plugin 该做桥，不该做脑
2. 复杂业务判断应该由：
   - authority anchor
   - project-scoped memory/knowledge
   - 长会话执行 agent
   来承担

## 8. 给 Claude 的评审问题

请重点审这 6 个问题：

1. 我对当前 substrate 成熟度的判断是否准确，尤其是 `project scope` 的现状判断
2. 把 `_project_context.md` 定位为长期 authority anchor 是否合理
3. `project_id` 贯穿主链是否应该优先于继续扩静态 context 文件
4. 上下文优先级合同是否还缺关键规则
5. promotion pipeline 的问题是否被正确定位为当前真正的中期瓶颈
6. 这个分阶段方案是否足够稳，不会再次走成一套项目专用补丁系统

## 9. 最终判断

一句话总结：

> 当前最正确的方向不是继续造一个项目专用上下文系统，而是保留一个永久的人类 authority anchor，然后把现有 `Harness / Memory / EvoMap / Context Assembler` 真正 project-scope 化。

这条路的重点不是“再发明能力”，而是“把已有基础设施真正用起来”。
