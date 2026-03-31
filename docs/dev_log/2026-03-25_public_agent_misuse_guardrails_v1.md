# Public Agent Misuse Guardrails v1

Date: 2026-03-25
Repo: ChatgptREST
Status: landed

## Why

过去数小时内出现了大量异常 `deep_research` public-agent sessions。排查后确认主要有两类误用：

1. 外部 caller 把 extractor / sufficiency gate 这类 pipeline 内部 microtask 包装成 public `advisor_agent_turn`。
2. 同一 caller 在短时间内重复重提等价的重型 `code_review/research/report` turn，造成 session 风暴和重复 `deep_research`。

另一个问题是 session 落盘里 caller 身份过于粗糙。public MCP 入口此前把所有请求都写成 `client.name=mcp-agent` / `instance=public-mcp`，难以区分到底是哪一个 MCP client 或 wrapper 在制造负载。

## What changed

### 1. Public MCP caller identity now survives ingress

`chatgptrest/mcp/agent_mcp.py`

- `advisor_agent_turn()` 不再把 caller 固定写成 generic `mcp-agent`。
- 现在会从 MCP `ctx.session.client_params.clientInfo` 和 `ctx.client_id` 提取：
  - `client.name`
  - `client.mcp_client_name`
  - `client.mcp_client_version`
  - `client.mcp_client_id`
- `client.instance` 仍保留 `public-mcp`，用于保留 public ingress lane 语义。

结果：

- `/v3/agent/turn` 的 `task_intake.context.client` 现在可以保留真实 MCP caller 身份。
- 后续排查 session 时，不再只能看到模糊的 `mcp-agent`。

### 2. Public advisor-agent now blocks obvious pipeline microtasks

`chatgptrest/api/routes_agent_v3.py`

新增 public-agent misuse guard：

- 仅对 public MCP ingress 生效。
- 对下列明显不应进入 public advisor-agent 的 prompt 直接返回 HTTP 400：
  - 结构化 extractor / JSON-only microtask
  - sufficiency gate（例如只回答 `sufficient/insufficient`）

返回错误：

- `error=public_agent_microtask_blocked`
- `error_type=PublicAgentMicrotaskBlocked`

目的：

- public advisor-agent 只接“用户可见的 end-to-end turn”
- pipeline 内部的 extraction / gating 必须留在 caller 自己的代码层或其他非 public substrate

### 3. Heavy duplicate public-agent submissions are deduped

`chatgptrest/api/routes_agent_v3.py`

新增 running-session duplicate guard：

- 仅对 public MCP ingress 生效。
- 仅对重型 `research/report/code_review` turn 生效。
- 基于同 caller + 同 goal_hint + 同消息正文 + 同 repo/provider 上下文做近窗判重。
- 命中后返回 HTTP 409，并直接给出已有 running session。

返回错误：

- `error=duplicate_public_agent_session_in_progress`
- `error_type=DuplicatePublicAgentSessionInProgress`
- `existing_session`
- `wait_tool=advisor_agent_wait`

目的：

- 防止 caller 在重型 turn 还没跑完时继续重复提交，制造多条等价 `deep_research`。

## Test coverage

新增 / 更新回归：

- `tests/test_agent_mcp.py`
  - public MCP 透传真实 caller identity
- `tests/test_routes_agent_v3.py`
  - block structured microtask on public agent ingress
  - reject duplicate running heavy public-agent session

执行：

- `./.venv/bin/python -m py_compile chatgptrest/mcp/agent_mcp.py chatgptrest/api/routes_agent_v3.py tests/test_agent_mcp.py tests/test_routes_agent_v3.py`
- `./.venv/bin/pytest -q tests/test_agent_mcp.py tests/test_routes_agent_v3.py`

## Residual limits

- 这次只收口 public-agent misuse 和 caller attribution，不处理 controller 自身为何把某些 code review 路由成 `deep_research`。
- duplicate guard 是近窗护栏，不是全局幂等替代；正常的显式 `session_id` patch/resume 语义保持不变。
