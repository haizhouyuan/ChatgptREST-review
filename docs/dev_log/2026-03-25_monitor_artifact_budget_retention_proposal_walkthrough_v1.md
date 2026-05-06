# ChatgptREST Monitor Artifact Budget / Retention Proposal Walkthrough v1

> 日期: 2026-03-25
> 范围: `artifacts/monitor/*` 只读盘点与 proposal
> 结果: 完成 budget / retention tiers / future cleanup guards 文档，无执行性清理动作

## 1. 本轮做了什么

本轮只做了两件事：

- 只读盘点 `/vol1/1000/projects/ChatgptREST/artifacts/monitor/*`
- 把结果收成 `docs/ops/2026-03-25_monitor_artifact_budget_retention_proposal_v1.md`

同时在 `docs/README.md` 的 ops 导航里补了该提案入口。

## 2. 本轮最重要的事实

### 2.1 fresh worktree 不自带 shared runtime artifacts

在新的 clean worktree 里，`artifacts/monitor/` 并不存在。

这说明：

- worktree 是代码施工面
- shared runtime artifacts 仍然挂在主仓根路径
- 只读盘点必须指向 `/vol1/1000/projects/ChatgptREST/artifacts/monitor/*`

这个事实和先前的 worktree policy 是一致的，也再次说明：

- 后续涉及 runtime evidence 的治理，不能假设“换个 worktree 就看不到真实占用”

### 2.2 当前最大容量源不是 incident pack

本轮盘点确认：

- `artifacts/monitor/` 总量约 `128G`
- `maint_daemon` 约 `120G`
- `maint_*.jsonl` 总量约 `95G`
- `maint_daemon/incidents/` 约 `25G`

所以当前最大热点是：

- recent rolling JSONL

而不是：

- historical incident evidence

### 2.3 单纯 `>30d` 清理不会解决问题

只读统计显示：

- `maint_daemon` 30 天以上文件只占约 `5.37%`
- 30 天以上字节量只占约 `0.89%`

这意味着后续 cleanup 若只做：

- `find ... -mtime +30`

在当前阶段几乎不会明显减压。

## 3. 本轮因此给出的 proposal 口径

proposal 里明确了 4 层对象：

- canonical incident evidence
- high-volume rolling telemetry
- bounded rolling health signals
- analytical / review bundles

并明确：

- 未来 cleanup 第一治理对象应是 `maint_daemon/maint_*.jsonl`
- 第二治理对象应是 `periodic/*.jsonl`
- `incidents/*` 不能被普通 rolling janitor 直接处理

## 4. 本轮刻意没有做的事

这轮没有做：

- 删除任何 monitor 文件
- 压缩任何 JSONL
- 迁移任何 artifact root
- 改 systemd / timer / daemon 行为
- 改 `maint_daemon.py`
- 写 janitor 脚本

原因是这轮的目标是：

- 先把边界、预算和 guard 说清楚

而不是：

- 未经批准就开始清理

## 5. 一句话结论

> 这轮把 `artifacts/monitor/*` 的容量问题从“抽象 retention 讨论”收敛成了一个可执行 proposal：真正的主热点是最近 30 天的 rolling JSONL，不是老 incident pack；后续 cleanup 必须先围绕这个判断来设计。
