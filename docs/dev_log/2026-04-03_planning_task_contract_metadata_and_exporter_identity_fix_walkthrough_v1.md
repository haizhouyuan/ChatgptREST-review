# 2026-04-03 Planning Task Contract Metadata And Exporter Identity Fix Walkthrough v1

## 本次做了什么

1. 继续推进 `W2`，但没有再把它说成“task truth layer 已完成”
2. 把七类 planning task 的 contract 做成 store / route / CLI 可见的 runtime metadata
3. 让 `checkpoint get/list` 不只是返回状态摘要，也返回更稳定的 handoff 线索
4. 顺手排查 acceptance/export 回归时发现：exporter 一直在裸调 `planning/task/{task_id}`，没带 identity params
5. 修掉 exporter 的 `lookup / after_writeback` 假阴性后，重新跑通 pack 回归
6. 再让 Maxwell 做了一轮 redteam，最终结论是 `approve-with-fixes`

## 为什么这一步有价值

这一步的价值不在于“继续堆更多 task type”，而在于把已经存在的七类 task 变得更容易跨端继续：

1. 现在下一端拿到 task payload 时，能看到它属于哪种 contract
2. 能知道默认输出目标和 checkpoint 版本
3. 能看到 continue / branch / writeback 的规则提示
4. acceptance exporter 重新变回可信的绿灯，而不是因为 identity 漏参出现假阴性

## 这次 redteam 的独立判断

我接受 redteam 的关键提醒：

1. 这批只能叫 `runtime-visible, persisted metadata`
2. 不能叫“执行性 contract engine 已完成”
3. `task_contract_version` 目前对旧记录仍带读时投影性质
4. exporter 的修复已经真实有效，但测试证明更偏 bundle-level，不是最窄单元回归

## 当前边界

这一步之后，`W2` 还剩：

1. 更强的 handoff/resume contract enforcement
2. route / CLI 三层更全面的七类 task 覆盖
3. 然后才能更稳地进入 `W3 OpenClawBot material intake`
