# ChatgptREST Agent Maintainer Entry Map Walkthrough v1

> 日期: 2026-03-25

这轮做的不是代码修复，而是把 ChatgptREST 这套“大仓库 + 多平面 + 多 worktree + 多关联库”的维护入口收成一个新 agent 可直接消费的地图。

## 本轮确认的事实

### 1. 主 worktree 当前是干净可工作的

除了 4 个历史 validation artifact 脏文件外，没有新的混杂逻辑改动。

### 2. 这个仓库实际上是 4 层系统叠在一起

- execution plane
- public advisor-agent surface
- OpenMind / advisor plane
- OpenClaw / finbot / controller plane

新 agent 之所以容易断点，核心原因不是“代码太多”本身，而是：

- 经常没先判断自己该进哪一层
- 会把 `theme-run`、`/v1/jobs`、`/v3/agent/turn`、`public MCP` 混成一个入口

### 3. worktree 生态非常复杂

不仅有主仓库：

- `/vol1/1000/projects/ChatgptREST`

还有：

- repo 内 `.worktrees/*`
- `/vol1/1000/projects/ChatgptREST-*`
- `/vol1/1000/worktrees/chatgptrest-*`
- `/tmp/chatgptrest-*`

这意味着新 agent 不适合“看见哪个 worktree 就直接进去改”。

### 4. 第一圈关联库已经明确

- `finagent`：研究引擎 / event mining / radar / deepen
- `openclaw`：agent hosting / orchestration 母体
- `chatgptMCP`：legacy fallback，不应误判为主系统

## 本轮产物

- `docs/dev_log/2026-03-25_chatgptrest_agent_maintainer_entry_map_v1.md`

## 建议的新 agent 最小入口

### 只想正确调用 ChatgptREST 的 agent

先读：

1. `AGENTS.md`
2. `docs/codex_fresh_client_quickstart.md`
3. `docs/runbook.md`

### 修 runtime / jobs / worker 的 agent

先读：

1. `docs/runbook.md`
2. `docs/contract_v1.md`
3. `docs/handoff_chatgptrest_history.md`

### 修 finbot / lane / commercial-space 的 agent

先读：

1. `ops/openclaw_finbot.py`
2. `chatgptrest/finbot.py`
3. `ops/controller_lane_wrapper.py`
4. `ops/controller_lane_continuity.py`

## 一句话收口

这轮不是给 ChatgptREST 再加一个新入口，而是先把“已有入口的层次和边界”固定下来。  
这样后续 agent 维护、升级、切 lane、做 discovery loop 时，能先从正确层面进入，而不是从错误的 surface 误入。
