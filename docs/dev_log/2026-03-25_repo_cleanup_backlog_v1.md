# ChatgptREST Repo Cleanup Backlog v1

> 日期: 2026-03-25
> 状态: backlog only
> 说明: 本文件只做分级，不执行任何清理动作

## 1. 低风险

这些可以在后续低风险任务里优先做：

- 在 `AGENTS.md` 和 `docs/README.md` 显式跳转到正式 maintainer entry
- 增加 worktree policy 文档
- 增加 artifact retention policy 文档
- 增加 cleanup backlog 文档
- 给 primary / admin / maintenance-only / legacy / retired 入口做文档矩阵
- 给入口脚本补轻量注释或 README 引导
- 把 `docs/dev_log` 中“history/proposal/reference/canonical”口径写清楚

## 2. 需确认

这些有价值，但必须二次确认后再做：

- 是否为旧 surface inventory 文档加“historical reference only”标记
- 是否对 `/tmp/chatgptrest-*` 做分类清单导出
- 是否对 `/vol1/1000/worktrees/chatgptrest-*` 建立 deployment/reference 标记表
- 是否给 `artifacts/monitor/*` 建 budget / retention proposal
- 是否给 `docs/dev_log/artifacts/*` 建 validation pack index
- 是否把 deprecated/primary matrix 落到单独文档

## 3. 高风险

这些必须单独立项，不属于当前任务：

- 删除任何 worktree
- 删除任何 artifact tree
- 删除 `.run/*`
- 删除 `state/*`
- 调整 systemd / timer / wrapper 指向
- 迁移运行中的 lane
- 改 `worker.py` / `routes_jobs.py` / `agent_mcp.py`
- 改 public MCP / `/v1/jobs` / advisor route 的行为分支

## 4. 本轮特别禁止

当前任务明确禁止：

- 删除目录
- 删除 worktree
- 删除 artifact tree
- 清理 `.run/*`

本轮只允许：

- 写文档
- 加 cross-link
- 加轻量注释
- 提 backlog

## 5. 一句话结论

> 现在需要的不是“开始清理”，而是先把能安全做的文档收口、分类与政策写完；真正删除动作必须另起一个经过确认的任务。
