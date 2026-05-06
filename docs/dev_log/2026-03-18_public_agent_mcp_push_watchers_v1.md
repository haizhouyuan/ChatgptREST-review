# 2026-03-18 Public Agent MCP Push Watchers v1

## 目标

把 public agent MCP 从“长任务前台同步等待”收成“立即返回 + 后台 watcher + 完成通知”的交互。

这次只改：

- `chatgptrest/mcp/agent_mcp.py`
- `tests/test_agent_mcp.py`

不改：

- `/v3/agent/*` 主 REST 契约
- public agent tool surface（仍然只有 `advisor_agent_turn/status/cancel`）

## 问题

Claude Code / Codex 通过 `advisor_agent_turn` 调长任务时，经常显式传：

- `delivery_mode="sync"`
- `goal_hint="research"`
- `timeout_seconds=600`

此前 public MCP 只是把这次调用原样转发到 `/v3/agent/turn`。

结果是：

- 前台 tool call 会一直卡住
- Claude Code 会显示 `Running...`
- 如果 transport 中断，还会造成“任务在后端跑、前端以为失败”的错觉

服务端其实已经有：

- `delivery_mode=deferred`
- `stream_url`
- `/v3/agent/session/{session_id}/stream`

但 public MCP 这层没有自动消费这些能力。

## 改动

### 1. 长任务自动后台化

对以下 `goal_hint`：

- `research`
- `gemini_research`
- `gemini_deep_research`
- `consult`
- `dual_review`
- `report`
- `write_report`

当 client 请求 `delivery_mode="sync"` 时，public MCP 现在会自动改成：

- `delivery_mode="deferred"`

并在返回体里显式写：

- `delivery_mode_requested`
- `delivery_mode_effective`
- `auto_background_reason=long_goal_auto_background`

这让现有 CC/Codex 提示词不用立刻全部重写，也不会继续把长任务卡在前台。

### 2. MCP 内置 background watcher

`advisor_agent_turn` 在 deferred 成功返回后，会自动起 watcher：

- 记录 `watch_id`
- 优先消费 `stream_url` 对应的 SSE
- 若未进入终态，则再回查 `/v3/agent/session/{session_id}`
- 完成后把结果存到本进程内 watcher state

### 3. 完成通知

如果设置了 `CODEX_CONTROLLER_PANE`，watcher 完成时会调用 tmux message：

- `[chatgptrest-agent] session done: ...`

也就是：

- 前台不再一直卡着
- 完成时会有“推送效果”

### 4. `advisor_agent_status` 带回 watcher 状态

现在 `advisor_agent_status(session_id)` 会附带：

- `watch_id`
- `watch_status`
- `background_watch`

如果远端 session 查 404，但本地 watcher 已经拿到终态结果，也会优先返回 watcher 缓存的结果。

## 测试

本轮新增/更新测试：

- `test_agent_mcp_turn_auto_backgrounds_long_research_goal`
- `test_agent_mcp_status_includes_background_watch_state`

回归：

- `tests/test_agent_mcp.py`
- `tests/test_bi09_mcp_business_pass.py`

## 范围说明

这次实现的是：

- public MCP 层的自动后台 watcher
- 对 coding agent 的“推送式完成通知”

还不是：

- 真正的跨进程 durable watcher registry
- 任意 MCP client 的 out-of-band callback
- `/v3/agent/*` session persistence

如果后续要进一步强化：

1. 可把 watcher state 持久化到 DB/SQLite
2. 可把 tmux notify 扩展成更通用的 controller callback
3. 可把 long-goal auto-background 策略下沉到 policy table
