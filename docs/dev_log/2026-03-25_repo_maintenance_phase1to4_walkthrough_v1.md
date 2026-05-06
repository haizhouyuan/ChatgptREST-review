# ChatgptREST Repo Maintenance Phase 1-4 Walkthrough v1

> 日期: 2026-03-25
> 范围: 文档收口 / policy / inventory / backlog
> 结果: 完成 docs-only 第一轮交付，无运行时改动

## 1. 本轮交付了什么

新增：

- `docs/dev_log/2026-03-25_chatgptrest_low_risk_repo_maintenance_plan_v2.md`
- `docs/ops/2026-03-25_agent_maintainer_entry_v1.md`
- `docs/ops/2026-03-25_worktree_policy_v1.md`
- `docs/ops/2026-03-25_artifact_retention_policy_v1.md`
- `docs/dev_log/2026-03-25_repo_cleanup_backlog_v1.md`

轻量更新：

- `AGENTS.md`
- `docs/README.md`

## 2. 为什么这样拆

本轮遵守了评审后确认的执行口径：

- 不做任何删除
- 不动 `.run/`
- 不改 systemd / timer / wrapper 指向
- 不改 `worker.py` / `routes_jobs.py` / `agent_mcp.py`
- 只做文档、cross-link、分类和 backlog

所以交付顺序是：

1. 先把 plan 调整成 v2
2. 再把 maintainer entry 正式提升到 `docs/ops/`
3. 再把 worktree / retention policy 独立成可执行文档
4. 最后给出 cleanup backlog

## 3. 关键变化点

### 3.1 `.run/` 被单独提升为 live runtime state

这轮没有把 `.run/` 混进普通 retention 对象，而是单独写成：

- live runtime state
- 禁止按“老文件清理”处理
- 只能在服务停稳或 runbook 明确指示下处理

### 3.2 maintainer entry 升格到了 `docs/ops/`

没有把正式入口继续留在 `docs/dev_log/`，也没有塞进 `docs/` 根平铺，而是：

- 新增 `docs/ops/2026-03-25_agent_maintainer_entry_v1.md`
- 由 `AGENTS.md` 和 `docs/README.md` 显式跳转

### 3.3 worktree policy 明确了 `/vol1/1000/worktrees/` 的特殊类别

本轮把它明确定义为：

- possible stable deployment
- long-lived task worktrees

并加了删除前必须核对 systemd / wrapper / runbook / `git worktree list` 的预检查口径。

## 4. 本轮没有做什么

没有做的动作同样重要：

- 没有删除任何 worktree、目录、artifact tree
- 没有清理 `artifacts/monitor/`
- 没有处理 `.run/*`
- 没有处理 `state/*`
- 没有处理主仓当前 4 个历史 validation artifact 脏文件
- 没有改任何运行时行为逻辑

## 5. 对 ChatgptREST 和其他 Codex 的影响判断

按本轮实际执行内容判断：

- 不会影响 ChatgptREST 正常工作
- 不应影响其他正在本仓工作的 Codex

原因：

- 本轮只有文档和 cross-link 变更
- 没有 service 重启
- 没有 runtime state 处理
- 没有 worktree 删除
- 没有入口行为分支修改

## 6. 下一步应当怎么做

如果继续推进，优先顺序仍应保持：

1. 进一步补充 deprecated / primary entrypoint 文档矩阵
2. 只在脚本头部加轻量注释，不改运行分支
3. 维持 cleanup backlog 为 proposal，不做执行

真正删除、迁移、归档相关动作，必须另起一个经过确认的后续任务。
