# 2026-03-31 Controller Session Status And Wait Refresh Hardening v1

## 背景

在真实外部调研任务里，public advisor-agent MCP 出现了一类误导性状态：

- 底层 provider job 已经进入 `blocked`
- child job 已经可推导成 `needs_followup`
- 但 `/v3/agent/session/{id}` 仍显示 `running`
- `advisor_agent_wait` 也可能因为 SSE 返回了非空但陈旧的 `running` snapshot，最终给出 `timeout`

典型会话：

- `session_id=agent_sess_deb9ecef012748ae`
- `run_id=5ae399667c7646c9bfda8d9fd9fce05a`
- `job_id=72d5fbf5f28340c4b511e8a5e0c1a9ec`

对应 evidence 里，job events 已明确记录：

- `status_changed: in_progress -> blocked`
- `issue_auto_reported`
- `auto_autofix_submitted`

## 根因

根因有两层：

1. `routes_agent_v3._controller_snapshot()` 只信 controller snapshot，没有把 child job 的 terminal-ish blocker/followup 状态折叠回 public session 视图。
2. `agent_mcp.advisor_agent_wait()` 在 `_wait_stream_terminal()` 返回了非空 snapshot 时，不会再做一次最终 `/session` refresh；如果 SSE 返回的是陈旧 `running` 数据，就会把 stale 状态当最终结果。

## 修复

### 1. Controller session 允许 fallback 到 child job

文件：

- `chatgptrest/api/routes_agent_v3.py`

动作：

- `_controller_snapshot(..., fallback_job_id="")`
- 优先从 `run.final_job_id` / `delivery.job_id` / `session.job_id` 找 child job
- 当 controller 仍是 `running/failed`，但 child job 已经给出 terminal-ish `agent_status` 时，优先折叠 child snapshot
- 保留 child `conversation_url`
- 同步构造 `same_session_repair` `next_action`
- 把 `retry_after_seconds` / `last_error_type` 带回 public session

### 2. MCP wait 总是做最终 refresh

文件：

- `chatgptrest/mcp/agent_mcp.py`

动作：

- `advisor_agent_wait()` 在 `_wait_stream_terminal()` 之后，无论 SSE 是否返回非空 snapshot，都额外做一次 `_session_status()` refresh
- 当 refreshed snapshot 比 SSE snapshot 更新，或 refreshed 已 terminal 时，优先使用 refreshed

## 新增回归

- `tests/test_routes_agent_v3.py::test_get_session_promotes_child_job_needs_followup_when_controller_snapshot_is_stale`
- `tests/test_agent_mcp.py::test_agent_mcp_wait_prefers_fresh_terminal_session_over_stale_stream_snapshot`

## 验证

定向验证覆盖：

- stale controller snapshot 下，`get_session` 会从 child job 折叠成 `needs_followup`
- stale SSE snapshot 下，`advisor_agent_wait` 会优先使用 fresh terminal session
- 既有 `cancelled` 抗 stale 回归仍然保持
- 既有 `timeout for non-terminal session` 回归仍然保持

## 影响边界

影响点集中在 public advisor-agent 状态折叠与 MCP wait 收尾，不改变：

- provider job 执行语义
- worker blocked / autofix 语义
- controller 内部状态机

## 后续

这次修复后，外部长任务工作流遇到 provider blocked / verification page 时，public session 与 MCP wait 不应再长期停留在误导性的 `running/timeout` 组合上；后续如果仍出现类似症状，应优先检查：

- child job 是否缺 `job_id`
- controller snapshot 是否丢 `delivery`
- session refresh 是否被 transport error 中断
