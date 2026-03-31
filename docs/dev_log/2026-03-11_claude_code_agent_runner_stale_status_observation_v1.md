---
title: Claude Code Agent Runner Stale Status Observation
version: v1
updated: 2026-03-11
status: completed
---

# 背景

为补齐 `slice_c2_reducer_reviewpack` 的 metadata-first 小切片，我没有继续沿用早期不稳定 wrapper，而是用受控 runner 重发了一个更小任务：

- run_id: `ccjob_20260311T004710Z_7548ef4b`
- prompt:
  `/vol1/1000/projects/ChatgptREST/artifacts/monitor/planning_history_agent_teams/20260311T080541/prompts_v3/slice_c2_reducer_reviewpack_small.txt`

# 观测结果

启动后，runner 返回：

- `state=queued`
- 随后变为 `state=running`

但后续实查发现：

1. `worker_pid` 和 `cmd_pid` 对应进程已经消失；
2. `status/status.json` 仍停留在 `running`；
3. `stdout.log` / `stderr.log` 均为空；
4. `result/` 目录没有任何结果文件；
5. `worker.log` 只有一条 `queued` 记录，没有终态记录。

# 结论

这个样本说明：

- 受控 runner 比旧 wrapper 更容易定位状态文件位置；
- 但当前 runner 仍然存在 **“进程已退出但状态文件未终态化”** 的问题；
- 因此今后不能只信 `status.json` 的 `state=running`，还必须同时校验：
  - pid 是否存活
  - heartbeat 是否更新
  - stdout/stderr/result 是否有实际推进

# 对后续 agent teams 的操作约束

1. `status=running` 不是充分条件。
2. 若 `pid` 已退出且 `status` 未更新，必须判定为 stale run。
3. stale run 应进入：
   - `failed_preflight`
   - 或 `unknown_failed`
   而不是一直保留 `running`。
4. 对长期分析任务，主控必须做三重校验：
   - 状态文件
   - pid 存活
   - 结果/日志是否增长

# 建议

## 1. runner 层

- 增加 stale heartbeat 检测
- 增加 pid liveness 检测
- 若 cmd 进程消失且无结果，自动把状态推进到失败终态

## 2. orchestrator 层

- 不允许只根据 `status=running` 长时间等待
- 必须设置超时与 fallback 路径

## 3. 文档与 runbook

- 后续任何 agent teams 运行记录里，都要单独记录：
  - `run_id`
  - `status_file`
  - `pid`
  - `stdout/stderr/result`
  - stale 判定结果

# 本次任务中的处理

本次我将这个 runner 样本视为：

- 一个有效的失败观测
- 一个对未来 teams 实践有价值的经验

但不再让主线报告等待它恢复。`planning` 谱系和 EvoMap 入库策略的主结论，继续以前面已经成功的切片结果与 deterministic bootstrap 为准。

