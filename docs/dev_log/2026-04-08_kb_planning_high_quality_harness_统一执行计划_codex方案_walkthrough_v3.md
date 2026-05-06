# KB + Planning High-Quality Harness 统一执行计划 Codex方案 Walkthrough V3

Date: 2026-04-08

## 本次变更

这版 `walkthrough v3` 只做一件事：把统一执行计划从“方向正确”推进到“实施无歧义”。

相对 `v2`，本次补了 6 个执行级冻结点：

1. `KB Hub / EvoMap / planning runtime pack` 的真实子系统边界
2. `planning explicit surface` 的引入与 `USER_HOT_PATH` 不变约束
3. `family-aware groundedness` 的冻结权重
4. dataset assertion schema
5. fallback 风险护栏
6. `EvoMap vector lane + answer_feedback/scorer wiring` 的显式子阶段

## 为什么这样做

当前剩余工作已经进入高风险主链：

- retrieval surface
- context injection
- vectorization
- telemetry / feedback

如果不把这些细节冻结，后续 sidecar 并行评测和主链实现会在执行过程中漂移，导致：

1. `plane` 口径和真实 DB/入口混淆
2. groundedness 权重实现时走样
3. fallback 范围意外扩大到默认 hot path
4. dataset 验证口径不统一
5. feedback 与 interaction learning 混成一团

## 接下来怎么执行

1. 先起 `claudeminmax` sidecar，收 dataset/assertion/抽样审计
2. 我自己实现 retrieval/provenance/vector/feedback 主链
3. 之后一起做 integrated acceptance 和最终 closeout
