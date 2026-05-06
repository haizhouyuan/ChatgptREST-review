# 2026-04-07 Project-Scoped Substrate Adoption Plan Walkthrough v1

日期：2026-04-07

## 为什么补这份文档

本轮讨论已经超出当前 planning 两个项目，问题变成：

1. 现有 `Harness / Memory / EvoMap / Context Assembler` 到底还有没有长期价值
2. 项目上下文要不要继续靠 `_project_context.md`
3. 自我进化是不是现在就该做主线

需要一份基于真实代码和真实数据库状态的 adoption plan，而不是只停在架构想法。

## 这次确认的关键事实

1. `Memory / Context / EventBus / EvoMap` 都已经是实装能力，不是概念
2. `project` 维度在 EvoMap 里已经存在，真实库也已有大量 `scope_project=planning` atoms
3. 真正缺的是 project scope 没有贯穿到 `ContextResolver / ContextAssembler / MemoryManager` 主链
4. `openmind-memory` 的 auto-capture 现在只能算轻量 session memory，不是 authority truth
5. 当前更现实的中期瓶颈是 promotion pipeline 吞吐太低，而不是“没有自我进化框架”

## 这份方案的核心判断

1. `_project_context.md` 不应该继续做项目缓存
2. 但它应该长期保留为 authority anchor
3. 现有 substrate 应该被 project-scope 化，而不是被新系统替代
4. dynamic assembly 之前必须先写死 authority 优先级
5. harness-driven self-improvement 要放在 promotion pipeline 恢复之后

## 输出

正式评审文档：

- `docs/reviews/2026-04-07_project_scoped_substrate_adoption_plan_for_claude_v1.md`

## 预期用途

让 Claude Code 重点审核：

1. 当前 substrate 成熟度判断是否准确
2. `_project_context.md` 的永久定位是否合理
3. `project_id` 贯穿主链是否是当前最正确的实际动作
4. 这个分阶段方案会不会再次走偏成一套新的项目专用补丁系统
