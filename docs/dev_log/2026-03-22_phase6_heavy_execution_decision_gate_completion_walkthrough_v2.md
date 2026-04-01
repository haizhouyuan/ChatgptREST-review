# 2026-03-22 Phase 6 Heavy Execution Decision Gate Completion Walkthrough v2

## 为什么补 v2

`v1` 的问题不是主裁决错了，而是 live-state 压缩过度。

我重新回到 [engine.py](/vol1/1000/projects/ChatgptREST/chatgptrest/controller/engine.py) 核了 `_resolve_execution_kind()`，确认 reviewer 指出的事实成立：

- 当 `cc_native` 已注入
- 且 route in `{funnel, build_feature}`
- 即使没有显式 `team` / `topology_id`

controller 仍会返回 `team`。

这说明：

- 当前有 explicit operator surface
- 但也还有 implicit controller fallback

所以 `v1` 把 heavy execution 写成“显式 opt-in 实验层”是不够精确的。

## 这轮改了什么

这轮没有改代码行为，只改决策文档口径。

修正后的表述是：

- heavy execution 当前应被视为 `gated experimental lane`
- canonical scenario packs 继续明确站在 `job`
- controller 的隐式 `funnel/build_feature -> team` fallback 仍被视为 residual live behavior

## 为什么我没有去改实现

因为 `Phase 6` 的目标是裁决，不是实现调整。

如果这轮直接去改 controller，把 implicit fallback 拔掉，会把两个问题混在一起：

1. `Phase 6` 的独立判断是否成立
2. controller 的 team fallback 是否应该在下一轮收口

这两个问题不该在同一轮里混做。

当前更干净的处理是：

- 先把事实写准
- 保留 `NO-GO` 主裁决
- 后续如果要真的把 heavy execution 改成 explicit-only，再开单独实现轮次

## 最后结论

`Phase 6` 现在的稳定口径是：

- 不扶正 Work Orchestrator
- 保留现有 team/runtime 资产继续做 gated experimental lane
- 明确认账：今天还残留 controller 的 implicit route-based team fallback

所以这轮是一次 **precision fix**，不是方向翻盘。
