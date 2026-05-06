# 2026-04-03 Maxwell Redteam: Planning Agent 未完成部分全量实施计划 v6

## 审核对象

- [2026-04-03_planning_agent_full_unfinished_implementation_plan_v6.md](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-03_planning_agent_full_unfinished_implementation_plan_v6.md)

## 红队主要意见

Maxwell 的上一轮红队提出 8 条 finding。最关键的 2 条是：

1. 计划里的“当前状态冻结”已经落后于最新 evidence。
2. 第一阶段 gate 太松，按当时写法会存在误判通过空间。

除此之外，红队还指出：

1. `W1` 的问题定义说旧了，应该从“打通主链”改成“稳态化与 provider coverage”。
2. `W2` 漏写了当前已经存在的 `task_contract` 与 checkpoint query CLI。
3. `W3` 不应再把 ChatgptREST-native `Feishu WS gateway` 留作等价验收选项。
4. `W2` 和 `W6-S3` 有 ownership 重叠，需要把后者改成收尾裁剪。
5. `W4-S1` 不应完全后置，至少要与 policy 执行化并行。
6. 总结句不应继续把 `Anthropic harness / EvoMap` 混进 phase-1 完成判定。

## 我采纳的部分

这轮我独立核验后，采纳了下面这些点：

1. 现状冻结必须更新：
   - `OpenClawBot` 已有一条 `gemini-requested` live green
   - acceptance pack 已 7/7 全绿
   - continuity pack 已 3/3 全绿
2. 第一阶段 gate 必须收紧：
   - 不再是“至少 1 次 green”
   - 改成连续 3 次 green + live fail/cancel evidence + scope 明示
3. `W1` 改名并重写问题定义。
4. `W2` 明确把 `task_contract` 与 checkpoint query CLI 纳入真相层收口对象。
5. `W3` 测试与 evidence 只接受 `OpenClawBot owner path`。
6. `W6-S3` 改成收尾裁剪，不再和 W2 重叠。
7. `W4-S1` 前移到与 Phase C 并行。
8. `Anthropic harness / EvoMap` 明确写成 phase-1 后置项。

## 我没有原样照收的部分

红队整体方向我接受，但我的口径比它更收敛：

1. 我没有把当前状态改写成“已经接近日常可用”。
   原因是 live green 目前只明确覆盖 `gemini-requested` scope，不能把“局部已证实”说成“整体已站住”。
2. 我也没有把 `W1-S4` 材料类型覆盖完全前移。
   它仍然更适合作为主链稳态化后的边界冻结项，而不是当前第一优先 blocker。

## 结论

经过这轮红队吸收后，`v6` 才能作为当前 authoritative baseline 使用：

- 它不会再把过时状态当现状
- 它不会再用过松 gate 给自己留假通过空间
- 它把 phase-1 scope 收得更清楚
- 它把后续所有代码开发重新压回到真正未完成的主线上
