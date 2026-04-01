# Public Agent Misuse Guardrails v2

Date: 2026-03-25
Repo: ChatgptREST
Status: landed + live-verified
Follow-up to: `docs/dev_log/2026-03-25_public_agent_misuse_guardrails_v1.md`

## Why v2 exists

v1 的代码方向是对的，但 live public MCP 复测没有马上签掉。根因后来确认不只是“service 还没重启”，而是 public MCP server 当时以 `stateless_http=True` 启动，导致 live 路径和单测假设脱节：

- `initialize` 不返回 `mcp-session-id`
- wrapper 拿不到真实的 MCP session header
- `ctx.session.client_params.clientInfo` 在 live 路径不可用
- public caller identity 在 session 落盘里继续退化成 generic `mcp-agent`
- duplicate heavy-turn guard 也会因为 public MCP 总是携带新 `session_id` 而被绕开

## What changed in v2

### 1. Public agent MCP is sessionful by default

`chatgptrest/mcp/agent_mcp.py`

- 新增 `_agent_fastmcp_stateless_http_default()`
- 默认返回 `False`
- 只有显式设置 `CHATGPTREST_AGENT_MCP_STATELESS_HTTP=1|true|yes|on` 才会退回 stateless mode

结果：

- live `initialize` 现在返回 `mcp-session-id`
- public MCP client 的真实 `clientInfo` / session metadata 可以进入 tool call context
- wrapper 和 direct MCP smoke 的行为重新与 repo validation harness 对齐

### 2. Duplicate guard now applies to caller-generated `session_id`

`chatgptrest/api/routes_agent_v3.py`

此前 duplicate guard 的入口条件是：

- `if not body.get("session_id")`

但 public MCP 的 `advisor_agent_turn()` 会为每次 turn 自动生成并发送 `session_id`，所以 live public-MCP 客户端天然绕开 dedupe。

现在改为：

- 只有“请求命中的 `session_id` 已经对应一个现存 session”时，才视为 resume/patch 并跳过 dedupe
- 任何“caller 新生成的 fresh session_id” 仍然参与 duplicate guard

结果：

- public MCP caller 即使每次都带不同 `session_id`，重复提交等价的重型 `research/report/code_review` turn 仍会收到 `duplicate_public_agent_session_in_progress`

## Live verification

在新进程重启后做了 live public-MCP 验证：

1. `POST /mcp` `initialize`
   - 响应包含 `mcp-session-id`
2. direct MCP `advisor_agent_turn`
   - 新 session 的 `task_intake.context.client` 里能看到真实 `mcp_client_name/mcp_client_version`
3. 同 caller + 同 heavy code-review prompt 连续提交两次
   - 第一条 accepted
   - 第二条返回 HTTP 409 `duplicate_public_agent_session_in_progress`

另外，live microtask prompt 在现网已经不会再被当成正常 long-running turn 收下；本轮 smoke 命中的是更早的 prompt policy block，而不是继续漏进 `deep_research`。

## Test coverage

新增 / 更新回归：

- `tests/test_agent_mcp.py`
  - public agent MCP `stateless_http` 默认关闭
  - env override 仍可显式开启 stateless mode
- `tests/test_routes_agent_v3.py`
  - duplicate heavy public-agent session guard 覆盖 caller 自带 `session_id` 的真实路径

执行：

- `./.venv/bin/python -m py_compile chatgptrest/mcp/agent_mcp.py chatgptrest/api/routes_agent_v3.py tests/test_agent_mcp.py tests/test_routes_agent_v3.py`
- `./.venv/bin/pytest -q tests/test_agent_mcp.py tests/test_routes_agent_v3.py`

## Outcome

这轮之后，public-agent misuse guardrails 不再只是“本地单测绿”。关键 live 行为现在也和预期对齐：

- public MCP sessionful handshake 生效
- caller identity 能真实透传
- duplicate dedupe 不再被 caller-generated `session_id` 绕开
