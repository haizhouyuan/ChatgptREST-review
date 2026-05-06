# ChatgptREST 低风险仓库整顿计划 Walkthrough v1

> 日期: 2026-03-25
> 任务类型: 调查 + 计划落文档
> 结果: 完成计划文档首版，未触碰运行时行为

## 1. 本轮做了什么

本轮没有做仓库清理、没有动运行面代码、没有改 systemd，也没有处理主仓现有 4 个历史 validation artifact 脏文件。

实际完成的是两件事：

1. 按指定顺序做只读调查
2. 把调查结论收敛成一份可审核的总计划文档

产物：

- `docs/dev_log/2026-03-25_chatgptrest_low_risk_repo_maintenance_plan_v1.md`

## 2. 按要求先读的文档

已按顺序阅读：

1. `AGENTS.md`
2. `docs/runbook.md`
3. `docs/contract_v1.md`
4. `docs/client_projects_registry.md`
5. `docs/handoff_chatgptrest_history.md`
6. `docs/dev_log/2026-03-25_chatgptrest_agent_maintainer_entry_map_v1.md`

为避免重复造轮子，还补读了：

- `README.md`
- `docs/README.md`
- `docs/2026-03-17_mcp_and_api_surface_inventory_v1.md`
- `docs/2026-03-17_public_agent_mcp_default_cutover_v1.md`
- `docs/2026-03-16_finbot_continuous_runtime_rollout_v2.md`
- `docs/roadmaps/2026-03-16_artifact_governance_blueprint_v2.md`

## 3. 调查方式

本轮只做只读盘点，主要看了 4 组事实：

1. 当前工作树状态
2. 仓库目录与 worktree 分布
3. artifact / state / docs 盘面体量
4. 关联库边界和既有入口文档

关键只读命令包括：

- `git status --short`
- `git worktree list --porcelain`
- `find . -maxdepth 2 -type d`
- `du -sh artifacts state .run logs docs/dev_log`
- `du -sh artifacts/monitor/* artifacts/jobs docs/dev_log/artifacts/*`

## 4. 核心发现

### 4.1 当前主仓脏状态

主仓当前只有 4 个已知历史 artifact 脏文件：

- `docs/dev_log/artifacts/phase11_branch_coverage_validation_20260322/report_v1.json`
- `docs/dev_log/artifacts/phase11_branch_coverage_validation_20260322/report_v1.md`
- `docs/dev_log/artifacts/phase13_public_agent_mcp_validation_20260322/report_v1.json`
- `docs/dev_log/artifacts/phase13_public_agent_mcp_validation_20260322/report_v1.md`

本轮保持不碰。

### 4.2 worktree 生态已经超过“临时开发目录”规模

观察到同时存在：

- 主仓
- repo 内 `.worktrees/*`
- repo 邻近 `ChatgptREST-*`
- `/vol1/1000/worktrees/chatgptrest-*`
- `/tmp/chatgptrest-*`
- 少量 detached / 其他路径

这意味着：

- worktree 不能粗暴按“主仓 vs 临时目录”二分
- 必须先做分类清单，再谈删除或归档

### 4.3 retention 大头在 runtime monitor，不在文档包

本轮最重要的容量发现是：

- `artifacts/monitor`: `128G`
- 其中 `artifacts/monitor/maint_daemon`: `120G`
- `artifacts/jobs`: `7.7G`
- `docs/dev_log/artifacts`: `2.5M`

所以第一轮 retention policy 必须优先解释 runtime monitor，而不是把注意力放错到 `docs/dev_log/artifacts`。

### 4.4 当前问题是入口收口，不是功能缺口

从 `AGENTS.md`、`runbook.md`、`contract_v1.md`、`client_projects_registry.md`、entry map 和 surface inventory 看，默认入口结论其实已经存在，但还没有被压成一套对新维护 agent 足够稳定的入口层。

## 5. 为什么本轮没有直接改别的

原因有 4 个：

1. 任务明确要求先做低风险调查和计划，不是直接清理
2. `routes_jobs.py`、`worker.py`、`agent_mcp.py` 被明确列入首轮禁改
3. worktree 与 runtime worktree 之间有真实部署历史，误删风险高
4. retention 目前缺的是 maintainer-facing policy，不是先上自动清理脚本

## 6. 计划文档包含什么

计划文档里已经收口了：

- 任务目标与非目标
- 只读调查输入
- repo / plane / worktree / artifact / 关联库的调查结论
- 本轮问题定义
- 成功标准
- 建议交付物
- 建议执行顺序
- 建议提交粒度
- 待审核决策点

## 7. 本轮没有做的事

以下动作本轮都没有做：

- 没有删除 worktree
- 没有改 systemd
- 没有重启服务
- 没有改 `chatgptrest/worker/worker.py`
- 没有改 `chatgptrest/api/routes_jobs.py`
- 没有改 `chatgptrest/mcp/agent_mcp.py`
- 没有动 `finagent` / `openclaw` / `chatgptMCP`
- 没有处理那 4 个历史脏文件

## 8. 后续建议

下一步不应直接开始清理，而应先让你审核：

1. 交付物落点是否接受
2. worktree policy 是否把 `/vol1/1000/worktrees/` 视为特殊类别
3. retention policy 是否把 `artifacts/monitor/` 作为主治理对象
4. deprecated / primary entrypoint 标记首轮是否只做文档和轻量注释

审核通过后，再按计划文档中的分阶段顺序推进。
