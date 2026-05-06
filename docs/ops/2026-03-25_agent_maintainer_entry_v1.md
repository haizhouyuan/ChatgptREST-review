# ChatgptREST Agent Maintainer Entry v1

> 日期: 2026-03-25
> 目的: 给“接手维护 / 新开的 agent”一个正式入口，先判断 plane，再决定读什么、碰什么、绝不碰什么

## 1. 先给结论

ChatgptREST 不是单一服务，而是多平面叠加的仓库。

新维护 agent 进入本仓库后，第一件事不是找代码，而是先判断自己这次任务属于哪一层：

1. execution plane
2. public agent surface
3. advisor plane
4. controller / finbot plane
5. dashboard plane

如果不先判层，最容易发生 4 类错误：

- 用错 northbound/default entrypoint
- 在错误 worktree 里改代码
- 把运行态目录当成普通清理对象
- 把 ChatgptREST、finagent、openclaw 的边界混掉

## 2. 第一个 10 分钟该做什么

### Step 1: 先确认边界

只读执行：

```bash
git status --short --branch
git worktree list --porcelain
```

不要先做：

- 删除目录
- 清理 worktree
- 动 `.run/`
- 改 service / systemd / wrapper

### Step 2: 判定你要进哪个 plane

| 如果任务像这样 | 你应进入的 plane | 先看什么 |
|---|---|---|
| `/v1/jobs`、send/wait、blocked/cooldown、job artifact | execution plane | `docs/runbook.md`、`docs/contract_v1.md`、`docs/handoff_chatgptrest_history.md` |
| Codex / Claude Code / Antigravity 默认入口、public MCP surface | public agent surface | `AGENTS.md`、本文件、`docs/contract_v1.md` |
| advisor、report、funnel、memory、KB | advisor plane | `docs/runbook.md`、`chatgptrest/advisor/*`、`chatgptrest/kernel/*` |
| guardian / orch / finbot / controller lane | controller / finbot plane | `docs/runbook.md`、`ops/openclaw_*`、`chatgptrest/finbot.py` |
| 8787 dashboard、control plane read model | dashboard plane | `docs/runbook.md` dashboard 章节、`chatgptrest/dashboard/*` |

### Step 3: 记住默认入口

对 coding agent：

- 默认入口是 public advisor-agent MCP：`http://127.0.0.1:18712/mcp`
- 默认工具是：
  - `advisor_agent_turn`
  - `advisor_agent_status`
  - `advisor_agent_cancel`

不要默认从这些地方开局：

- `/v1/jobs kind=*web.ask`
- `/v3/agent/*` 裸 REST
- legacy bare MCP tools
- external `chatgptMCP`

## 3. 当前 canonical 入口矩阵

| 类别 | 当前 canonical 用途 | 路径 / 地址 | 说明 |
|---|---|---|---|
| Primary | coding-agent 默认 northbound surface | `http://127.0.0.1:18712/mcp` | public advisor-agent MCP |
| Primary | 统一运行/状态/作业 API | `http://127.0.0.1:18711` | FastAPI app |
| Internal | 内部 driver MCP | `http://127.0.0.1:18701/mcp` | worker / repair / maint 使用 |
| Admin-only | broad/internal MCP surface | `http://127.0.0.1:18715/mcp` | ops/debug 用，不是普通 agent 默认入口 |
| Maintenance-only | legacy jobs path | `chatgptrestctl --maintenance-legacy-jobs` | 仅受控维护场景 |
| Legacy fallback | 外部 `chatgptMCP` | `/vol1/1000/projects/chatgptMCP` | 默认不作为主系统 |
| Retired | legacy `chatgptrest-*` orch fleet | 见 runbook retired 章节 | 只读理解，不作为默认拓扑 |

## 4. 五个 plane 的代码入口

| Plane | 关键文件 / 目录 | 风险说明 |
|---|---|---|
| Execution | `chatgptrest/api/routes_jobs.py` / `chatgptrest/worker/worker.py` / `chatgptrest/executors/*` | 高风险，首轮默认只读 |
| Public agent | `chatgptrest/mcp/agent_mcp.py` / `chatgptrest/api/routes_agent_v3.py` | 高风险，首轮默认只读 |
| Advisor | `chatgptrest/advisor/*` / `chatgptrest/kernel/*` / `chatgptrest/kb/*` | 中高风险 |
| Controller / finbot | `ops/openclaw_*` / `chatgptrest/finbot.py` | 中高风险 |
| Dashboard | `chatgptrest/dashboard/*` / `chatgptrest/api/app_dashboard.py` | 中风险 |

## 5. 你现在不该碰什么

除非任务明确要求，否则默认不碰：

- `chatgptrest/worker/worker.py`
- `chatgptrest/api/routes_jobs.py`
- `chatgptrest/mcp/agent_mcp.py`
- systemd / timer / 端口 / service wrapper
- `.run/`
- `state/`
- `artifacts/jobs/`
- `artifacts/monitor/`
- `finagent` / `openclaw` / `chatgptMCP` 代码

## 6. 关联库边界

| Repo | 路径 | 默认理解 |
|---|---|---|
| finagent | `/vol1/1000/projects/finagent` | 上游研究引擎，默认只读 |
| openclaw | `/vol1/1000/projects/openclaw` | 编排母体，默认只读 |
| chatgptMCP | `/vol1/1000/projects/chatgptMCP` | legacy fallback，默认只读 |

如果你的问题需要跨库修复，先写清边界，再单独起任务；不要在本仓顺手扩到关联库。

## 7. 当前 worktree 判断口径

当前仓库同时存在：

- 主仓
- repo 内 `.worktrees/*`
- repo 邻近 `ChatgptREST-*`
- `/vol1/1000/worktrees/chatgptrest-*`
- `/tmp/chatgptrest-*`

默认口径：

- 主仓先只读理解
- `/vol1/1000/worktrees/` 视为 possible stable deployment / long-lived task worktrees
- `/tmp/` 默认当 scratch/historical，但仍然不能直接删

详细规则看：

- `docs/ops/2026-03-25_worktree_policy_v1.md`

## 8. 当前 artifact / runtime state 判断口径

最重要的不是“哪里文件多”，而是“哪些是 live runtime state，哪些是 evidence，哪些才适合讨论 retention”。

特别注意：

- `.run/` 是 live runtime state，不是普通 retention 对象
- `artifacts/monitor/` 是当前主要容量压力面
- `docs/dev_log/artifacts/` 体积不大，更偏审计/验证包

详细规则看：

- `docs/ops/2026-03-25_artifact_retention_policy_v1.md`

## 9. 继续往下读什么

建议顺序：

1. `docs/runbook.md`
2. `docs/contract_v1.md`
3. `docs/handoff_chatgptrest_history.md`
4. `docs/ops/2026-03-25_worktree_policy_v1.md`
5. `docs/ops/2026-03-25_artifact_retention_policy_v1.md`

如果只是要用 ChatgptREST，而不是维护它：

1. `docs/codex_fresh_client_quickstart.md`
2. `skills-src/chatgptrest-call/SKILL.md`
3. `docs/client_projects_registry.md`

## 10. 一句话结论

> 新维护 agent 想不迷路，先判 plane，再看 worktree 和 runtime state 边界；默认从 public advisor-agent MCP 和本文件切入，不要从低层 `/v1/jobs`、历史 broad MCP 或外部 fallback 开局。
