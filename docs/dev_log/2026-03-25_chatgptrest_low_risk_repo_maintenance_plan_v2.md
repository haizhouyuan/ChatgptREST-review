# ChatgptREST 低风险仓库整顿与维护入口收口计划 v2

> 日期: 2026-03-25
> 状态: approved with review adjustments
> 说明: 本版在 v1 基础上吸收评审意见，作为后续执行基线

## 1. 相比 v1 的 3 个硬调整

### 1.1 `.run/` 不再被视为普通 retention 对象

`.run/` 在后续 policy 中单独提升为：

- live runtime state
- 可能包含 pid、锁文件、browser/profile 指针、当前运行面协同状态

硬规则：

- 不能按“老文件清理”思路处理
- 只能在服务停稳或 runbook 明确指示下处理
- Phase 1-4 期间只允许写文档和说明，不允许清理 `.run/*`

### 1.2 正式 maintainer entry 的落点改为 `docs/ops/`

不再建议放到 `docs/` 根平铺。

正式落点调整为：

- `docs/ops/2026-03-25_agent_maintainer_entry_v1.md`

跳转方式：

- `AGENTS.md` 增加显式入口
- `docs/README.md` 增加显式入口

### 1.3 新增 Phase 1-4 的硬 no-delete guard

在本轮执行期间：

- 禁止删除任何 worktree
- 禁止删除任何目录
- 禁止删除任何 artifact tree
- 禁止删除 `.run/*`

只允许：

- 写文档
- 加 cross-link
- 加轻量注释
- 做 backlog 分类

真正删除、迁移、归档动作，必须另起一个经过确认的后续任务。

## 2. 维持不变的边界

以下边界与 v1 保持一致：

- 不做大功能开发
- 不改 public contract
- 不改默认端口、systemd 行为、运行时拓扑
- 不顺手修 unrelated bug
- 不动 finagent / openclaw / chatgptMCP
- 不处理主仓当前 4 个历史 validation artifact 脏文件
- 不改 `chatgptrest/worker/worker.py`
- 不改 `chatgptrest/api/routes_jobs.py`
- 不改 `chatgptrest/mcp/agent_mcp.py`

## 3. 更新后的交付物落点

| 交付物 | 目的 | 落点 |
|---|---|---|
| Maintainer entry | 正式维护入口 | `docs/ops/2026-03-25_agent_maintainer_entry_v1.md` |
| Worktree policy | worktree 分类与行为边界 | `docs/ops/2026-03-25_worktree_policy_v1.md` |
| Artifact retention policy | 保留策略与禁行动作 | `docs/ops/2026-03-25_artifact_retention_policy_v1.md` |
| Cleanup backlog | 后续动作分级 | `docs/dev_log/2026-03-25_repo_cleanup_backlog_v1.md` |
| Walkthrough | 执行记录 | `docs/dev_log/2026-03-25_repo_maintenance_phase1to4_walkthrough_v1.md` |

## 4. 更新后的执行顺序

仍按原顺序推进：

1. entry
2. worktree
3. retention
4. deprecated / primary entrypoint 标记
5. backlog

但执行期 guard 更硬：

- Phase 1-4 不做任何实际清理
- deprecated / primary 首轮只做文档矩阵和轻量注释
- `.run/` 与 runtime state 只观察，不处理

## 5. 一句话执行口径

> 这轮只收口文档、分类和政策，不做任何实际清理或运行时改动；`.run/` 视为 live runtime state，不按普通 retention 对象处理。
