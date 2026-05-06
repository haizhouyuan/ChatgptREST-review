# KB + Planning High-Quality Harness 统一执行计划 Codex方案 Walkthrough V1

Date: 2026-04-08

## 本次输出

生成一份统一执行计划：

- [2026-04-08_kb_planning_high_quality_harness_统一执行计划_codex方案_v1.md](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-08_kb_planning_high_quality_harness_统一执行计划_codex方案_v1.md)

## 为什么要单独做这份计划

当前两条线容易被分开讨论：

1. `KB / EvoMap / vector / promotion` 的治理
2. `planning / OpenClaw / Codex-grade harness` 的高质量闭环

但实际上这两条线不能分开做：

- 如果入口 harness 变强，而知识底座仍然脏、薄、错，执行端上限仍然被卡住。
- 如果知识底座治理了，但 ingress / route / closure / learning 仍然很弱，用户也感觉不到“变好”。

所以这次明确把两条线收进一个统一执行计划里。

## 本次最重要的决策

1. 认可 `claudeminmax` 适合作为 sidecar，但不做主链 owner。
2. Codex 继续主导：
   - 主链代码
   - promotion / retrieval / route 语义
   - 最终集成与验收
3. 计划被拆成：
   - KB 治理底座
   - planning harness 加固
   - OpenClaw / planning / KB 联动
   - 统一验收

## 计划文档重点

文档里已经明确写了：

1. 谁执行
2. 哪些可以并行
3. 哪些必须由 Codex 主导
4. 每个 phase 的测试方式
5. 每个 phase 的验收标准

## 备注

这份文档是执行计划，不是完成报告。后续如果真的启动执行，应继续按仓库纪律：

1. 每个有意义改动独立提交
2. 每个批次有 walkthrough
3. 最后做 scoped closeout
