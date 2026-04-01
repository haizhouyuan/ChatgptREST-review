# Public Agent Misuse Guardrails Walkthrough v2

Date: 2026-03-25
Repo: ChatgptREST

## Walkthrough

1. 先接住客户端复测反馈。
   v1 虽然代码和单测都过，但 live 服务还停在旧进程，而且 client 明确指出 duplicate dedupe 的 `session_id` 条件和 public MCP 的真实行为不一致。

2. 重新核对 live MCP 行为。
   直接对 `http://127.0.0.1:18712/mcp` 做 `initialize`，发现没有 `mcp-session-id` header；这说明 live public MCP 实际跑在 stateless 模式，caller identity 透传在现网天然打不到。

3. 把根因收在 public MCP 构造处。
   `chatgptrest/mcp/agent_mcp.py` 不再硬编码 `stateless_http=True`，改成默认 sessionful，仅保留显式 env override。

4. 同时修正 duplicate guard 判定。
   `chatgptrest/api/routes_agent_v3.py` 不再用“请求里有没有 `session_id`”判断是否跳过去重，而是用“这个 `session_id` 是否已经对应现存 session”判断是否属于真正的 resume/patch。

5. 跑定向回归。
   - `test_agent_mcp.py` 覆盖 sessionful 默认值
   - `test_routes_agent_v3.py` 覆盖 caller 自带 `session_id` 的 duplicate 路径

6. 重启 live 服务，再做真实 smoke。
   - `chatgptrest-api.service`
   - `chatgptrest-mcp.service`

7. 复验三个关键现象：
   - `initialize` 返回 `mcp-session-id`
   - session 落盘里 `task_intake.context.client` 带真实 MCP caller identity
   - 第二条等价 heavy turn 返回 `duplicate_public_agent_session_in_progress`

## Commands run

```bash
./.venv/bin/python -m py_compile \
  chatgptrest/mcp/agent_mcp.py \
  chatgptrest/api/routes_agent_v3.py \
  tests/test_agent_mcp.py \
  tests/test_routes_agent_v3.py

./.venv/bin/pytest -q tests/test_agent_mcp.py tests/test_routes_agent_v3.py

systemctl --user restart chatgptrest-api.service chatgptrest-mcp.service
```

## Outcome

这次不是再扩 guardrail 范围，而是把 v1 在 live 上落不实的两个薄点补齐：

- public MCP 的 session semantics 回到正确形态
- duplicate dedupe 终于覆盖到真实 public-MCP 客户端路径
