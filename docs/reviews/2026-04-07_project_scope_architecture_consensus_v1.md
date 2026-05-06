# Project Scope Architecture — Consensus v1

Date: 2026-04-07
Participants: Claude Code (claudegac), Codex
Status: consensus reached, pending implementation

## 共识结论

经过独立代码验证（Claude 通过代码分析，Codex 通过直接 DB 查询），双方在以下判断上达成一致：

### 核心判断

1. **不是缺基础设施，是已有基础设施没充分用起来。**
   - EvoMap: 103,871 atoms, 7,893 documents, 769MB 真实数据
   - MemoryManager: 成熟的 identity-scoping 模式（5 个维度）
   - EventBus / Observer / Signals: 真实运行中
   - Auto-capture: 真挂在 OpenClaw hooks 上

2. **`_project_context.md` 是永久的 authority anchor，不是临时缓存。**
   - 只放"系统不能自己决定"的东西：frozen_facts, style_rules, pinned authority docs
   - 不放可派生状态（当前阶段、最近修改等）
   - 不会被 V2/V3 替代

3. **project scope 是现有 substrate 的贯穿改造，不是一个大战略 phase。**
   - EvoMap schema 已有 `Document.project` 和 `Atom.scope_project`（118 个项目，26,120 个 atoms 有 scope_project）
   - graph_service 已支持 project_id 过滤
   - 缺的是：ContextResolveOptions、retrieval.py 主检索、MemoryManager、Signal 没有 project_id
   - 工作量：2-3 天 threading

4. **当前最大瓶颈是 promotion/消化链吞吐太低。**
   - 103,871 atoms 中只有 202 个 active（0.19%）
   - promotion_audit 只有 505 条记录
   - 系统在大量吞入但几乎不消化

### 上下文优先级合同（必须写死）

```
authority anchor > project memory > EvoMap knowledge > runtime heuristics
```

当不同来源冲突时，左边永远赢。这个合同必须在 project_id threading 时就落进 ContextAssembler 代码里。

### 最终架构：四层同时存在

| 层 | 来源 | 性质 | 谁能改 |
|---|---|---|---|
| Authority anchor | `_project_context.md` | 人工冻结的事实和规则 | 只有人 |
| Project memory | MemoryManager + project scope | 项目级工作记忆和决策历史 | 系统自动 + 人工修正 |
| Knowledge base | EvoMap + project scope | 跨 session 的结构化知识 | promotion pipeline |
| Runtime context | ContextAssembler | 组装后的上下文包 | 每次请求动态生成 |

这不是替代链（V0→V1→V2→V3），而是分层组合。

## 实施顺序

1. **立即做**：建好 `_project_context.md`（authority anchor），projectRef 注入上线
2. **Sprint 级别做**：给 MemoryManager / ContextResolveOptions / signals 贯穿 project_id
3. **Sprint 级别做**：让 retrieval.py 主检索吃到 scope_project
4. **同步写死**：上下文优先级合同落进 ContextAssembler
5. **后续优化**：promotion pipeline 吞吐率从 0.19% 提到 5-10%
6. **最后再谈**：harness-driven 自我进化

## 验证依据

### Claude 验证路径
- 通过 agent 分析 evomap/db.py, knowledge.py, context_service.py, memory_manager.py, context_assembler.py, signals.py, openmind-memory/index.ts
- 确认 schema 存在、数据真实、retrieval 不用 project scope

### Codex 验证路径
- 直接查询 /vol1/1000/projects/ChatgptREST/data/evomap_knowledge.db
- 确认 documents=7893, distinct project=91, atoms=103874, active=202, promotion_audit=505, scope_project非空=26120
- 确认 graph_service.py 和 routes_cognitive.py 已有 project_id
- 确认 ContextResolveRequest/Options 和 retrieval.py 没有 project_id
