# ChatgptREST Repo Maintenance Phase 1-4 Walkthrough v2

> 日期: 2026-03-25
> 范围: entry / worktree / retention / entrypoint matrix / backlog
> 结果: 完成 docs-only 第一轮交付，无运行时改动

## 1. 最终交付物

计划与记录：

- `docs/dev_log/2026-03-25_chatgptrest_low_risk_repo_maintenance_plan_v2.md`
- `docs/dev_log/2026-03-25_repo_cleanup_backlog_v1.md`

正式入口与 policy：

- `docs/ops/2026-03-25_agent_maintainer_entry_v1.md`
- `docs/ops/2026-03-25_worktree_policy_v1.md`
- `docs/ops/2026-03-25_artifact_retention_policy_v1.md`
- `docs/ops/2026-03-25_entrypoint_matrix_v1.md`

轻量跳转更新：

- `AGENTS.md`
- `docs/README.md`

## 2. 本轮确认下来的硬口径

### 2.1 `.run/` 不是普通 retention 对象

这轮已明确：

- `.run/` 是 live runtime state
- 不能按“老文件清理”处理
- 只能在服务停稳或 runbook 明确指示下处理

### 2.2 `/vol1/1000/worktrees/` 必须单列为特殊类别

这轮已明确：

- 它可能承载 stable deployment
- 也可能承载 long-lived task worktree
- 删除前必须核对 systemd / wrapper / runbook / `git worktree list`

### 2.3 deprecated / primary 首轮只做文档矩阵

这轮已明确：

- 先做 `entrypoint matrix`
- 不改任何运行时判断分支
- 不改 service / wrapper 指向

## 3. 本轮为什么安全

对 ChatgptREST 正常工作和其他 Codex 来说，本轮安全的原因是：

- 只有文档和 cross-link 变更
- 没有删除 worktree、目录、artifact tree
- 没有处理 `.run/*`
- 没有处理 `state/*`
- 没有重启服务
- 没有改 `worker.py` / `routes_jobs.py` / `agent_mcp.py`
- 没有改 public MCP / `/v1/jobs` / advisor route 的行为

## 4. 本轮没有做的事

这轮明确没有做：

- 真正 cleanup
- worktree 删除
- artifact 删除
- runtime state 处理
- cross-repo 改动

## 5. 后续任务口径

如果继续推进，下一轮也应保持：

- 文档矩阵和轻量注释优先
- 所有删除、迁移、归档动作另起任务
- 对 `.run/`、`state/`、`artifacts/jobs/`、`artifacts/monitor/` 继续保持“只观察、不处理”直到有单独批准
