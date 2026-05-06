# 2026-04-03 Planning Checkpoint Writeback Helper Walkthrough v1

## 1. 为什么现在做这一步

到 `master v7` 为止，phase-1 的主要 gap 已经不是：

1. 有没有 `task_id`
2. 有没有 `checkpoint`
3. `OpenClawBot` 能不能继续或取回

而是：

1. 深度工作台做了一轮真实工作后，怎么把结果显式写回同一条 task 线程

如果这一步不补，`task_id + checkpoint` 仍然更像入口侧能力，而不是多端共享能力。

## 2. 为什么用 script，而不是继续长 MCP

这一步故意没有做成：

1. `publicagentmcp` 新工具
2. `task_runtime` 前置依赖
3. 新 northbound surface

原因很直接：

1. 用户已经明确不想再把 public 面做成大杂烩
2. 这一步的真实需求只是 deep workbench 写回已有 sidecar
3. 一个本地 script/CLI helper 正好是最小承重形态

## 3. helper 做了什么

它做的事情很窄：

1. 接收 `task_id`
2. 接收本轮状态
3. 接收本轮最新输出或输出文件
4. 接收下一步建议
5. 接收 artifact refs
6. 调用 `MeetingTaskStore.update_checkpoint(...)`

## 4. helper 没做什么

它没做：

1. 自动识别任务
2. 自动选择 memory writeback
3. 自动决定 `new / continue / branch`
4. 自动归档所有草稿

所以这一步只是显式 writeback helper，不是新 orchestrator。

## 5. 当前最实用的用法

这一步之后，最朴素的工作流已经成立：

1. `OpenClawBot` 发起任务
2. 产出 `task_id`
3. `Codex / Claude Code / Antigravity` 深度推进
4. 完成一轮后用 helper 写回 checkpoint
5. `OpenClawBot` 再按 `task_id` retrieve

## 6. 风险边界

最大风险还是说重：

1. 容易把 helper 说成“自动多端连续性已经完成”

实际上更准确的是：

1. 现在只是把“多端共享同一 task sidecar”补到了可显式操作
2. 自动任务治理仍是后续工作
