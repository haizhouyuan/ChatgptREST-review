# 2026-03-22 Phase 6 Heavy Execution Decision Gate Completion v2

## 1. 为什么要出 v2

`v1` 的主裁决是对的，但把当前 heavy execution 说成“已经是显式 opt-in lane”说早了半步。

独立复核后，更准确的 live state 是：

- 存在显式 operator surface：
  - `/v2/advisor/cc-dispatch-team`
  - `/v2/advisor/cc-team-*`
- 但 controller 仍保留：
  - `route in {funnel, build_feature}` 的隐式 team fallback

所以当前应写成：

- `gated experimental lane`
- 不是 `fully explicit opt-in lane`

## 2. 本轮完成了什么

本轮完成的是一份修正后的准入裁决：

- 新增 [2026-03-22_heavy_execution_decision_gate_v2.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-22_heavy_execution_decision_gate_v2.md)
- 保留 `NO-GO` 主裁决
- 修正 Phase 6 的 live-state 口径：
  - 有 explicit control surface
  - 也有 residual implicit controller fallback

## 3. 这轮的独立判断

当前仓里的 team/runtime 资产仍然是真资产：

- `cc_native.dispatch_team`
- `TeamControlPlane`
- controller `team_execution`
- advisor `/cc-team-*` routes

但它们还不足以构成一个可扶正的 `Work Orchestrator`。

当前更准确的状态是：

1. canonical `planning / research` scenario packs 仍全部固定在 `execution_preference=job`
2. controller 还残留 `funnel/build_feature -> team` 的隐式 fallback
3. front door 还没有一套 first-class `HeavyExecutionSpec`
4. 低盯盘 supervision 还没成立
5. mixed-runtime proof 还没成立

所以当前正确决策仍然不是继续做大，而是把 heavy execution 明确冻结为 gated experimental lane。

## 4. 阶段验收

本阶段现在仍然已经能明确回答：

- 现在该不该扶正 `Work Orchestrator`
- 当前哪些 team/runtime 资产可以继续保留
- 哪些条件满足后才允许重开这条线

答案仍然清楚：

- **现在不该扶正**
- **只保留受限实验**
- **并承认当前还残留 implicit fallback，没有 fully explicit opt-in**

## 5. 对下一阶段的影响

这份修正不会把下一阶段拉回“再搭大平台”，相反会把后续目标收得更准：

- 如果以后真要把 heavy execution 扶正
- 先做掉 implicit fallback
- 再把 mixed-runtime prototype 和 OpenClaw-backed supervision 做出来

## 6. 结论

`Phase 6` 继续成立。

修正后的最终口径是：

- heavy execution 当前是 **gated experimental lane**
- 不是 **fully explicit opt-in lane**
- 更不是 **可以扶正的新中心**
