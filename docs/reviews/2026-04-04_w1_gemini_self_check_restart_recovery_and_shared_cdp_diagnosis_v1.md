# 2026-04-04 W1 Gemini self-check restart recovery and shared CDP diagnosis v1

## 1. 这批改动解决什么

这批不是宣布 `W1` 完成，而是把当前 live 链上的 Gemini 诊断面再往前推进一层：

1. `gemini_web_self_check` 不再只会在初始 prompt surface 丢失时立即失败。
2. MCP HTTP client 对一类真实出现过的 SSE/JSON-RPC 断裂增加 fresh-session retry。
3. public session projection 对 Gemini send-phase `cooldown / queued pause` 的 repair 语义继续收窄，避免把“无 provider-session 证据”的情况错误投影成需要人工接手。
4. live blocker 已经从“session surface 说不清”收窄到“Gemini live runtime/send path 仍不稳，且 send phase 还存在 blank cooldown/no-thread churn”。

## 2. 代码改动

本批只收了 4 个代码面：

1. [`chatgpt_web_mcp/providers/gemini/self_check.py`](/vol1/1000/projects/ChatgptREST/chatgpt_web_mcp/providers/gemini/self_check.py)
   - 增加 `_open_gemini_self_check_surface(...)`
   - 对初始 prompt surface `TargetClosedError` 做 reopen + best-effort local CDP Chrome restart
   - self-check 主流程改为走这个恢复入口
2. [`chatgpt_web_mcp/providers/gemini/ask.py`](/vol1/1000/projects/ChatgptREST/chatgpt_web_mcp/providers/gemini/ask.py)
   - 复用初始 prompt surface reopen / close helpers
   - 这批没有扩大 `_open_gemini_page(...)` 的 blast radius
3. [`chatgptrest/integrations/mcp_http_client.py`](/vol1/1000/projects/ChatgptREST/chatgptrest/integrations/mcp_http_client.py)
   - 对 `connection closed while reading from the driver`
   - `sse stream ended without a json-rpc response`
   - 增加 fresh-session retry
4. [`chatgptrest/api/routes_agent_v3.py`](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py)
   - `manual repair` marker 收窄
   - `queued pause / cooldown` 只有在 Gemini base app URL 且无 thread 证据时才投影为 same-session repair
   - `InfraError + Gemini infra text` 现在被显式纳入 send-phase same-session repair 判定

## 3. 新增/更新测试

### 3.1 新增

- [`tests/test_gemini_self_check_resilience.py`](/vol1/1000/projects/ChatgptREST/tests/test_gemini_self_check_resilience.py)
  - 覆盖 self-check 在 prompt surface `TargetClosedError` 后 reopen 成功
  - 覆盖 reopen budget 用尽后的 fail-closed

### 3.2 更新

- [`tests/test_gemini_provider_timeout_budget.py`](/vol1/1000/projects/ChatgptREST/tests/test_gemini_provider_timeout_budget.py)
- [`tests/test_mcp_http_error_propagation.py`](/vol1/1000/projects/ChatgptREST/tests/test_mcp_http_error_propagation.py)
- [`tests/test_routes_agent_v3.py`](/vol1/1000/projects/ChatgptREST/tests/test_routes_agent_v3.py)

## 4. 实际验证

这批实际跑过并通过：

```bash
./.venv/bin/pytest -q   tests/test_gemini_self_check_resilience.py   tests/test_gemini_provider_timeout_budget.py   tests/test_openclawbot_planning_task_plane_live_completion_gate.py   tests/test_routes_agent_v3.py   -k 'self_check or live_completion_gate or sse_end_cooldown_as_needs_followup or queued_send_pause_running_without_provider_session or infra_cooldown_as_needs_followup or reopen or initial_prompt or prepare_prompt'
```

以及：

```bash
./.venv/bin/pytest -q   tests/test_gemini_self_check_resilience.py   tests/test_mcp_http_error_propagation.py
```

## 5. live 现场核验

### 5.1 runtime 环境

当前 runtime env file 是：

- [`/home/yuanhaizhou/.config/chatgptrest/chatgptrest.env`](/home/yuanhaizhou/.config/chatgptrest/chatgptrest.env)

其中当前确认存在：

- `CHROME_DEBUG_PORT=9226`
- `CHATGPT_CDP_URL=http://127.0.0.1:9226`
- `GEMINI_CDP_URL=http://127.0.0.1:9226`

本批还做了一个运行时实验：

- `GEMINI_REUSE_EXISTING_CDP_PAGE=1`

该实验已经写入上述 env file，并重启过 `chatgptrest-driver.service`。

### 5.2 当前端口事实

现场多次核验得到：

- `9226` 是实际 Chrome CDP 端口
- `9222` 仍有一个长期存活的 `python3 -` 监听
- `18701` 是 driver
- `18711` 是 API
- `18712` 是 public MCP
- `18713` 是 node

### 5.3 当前 live 症状

这批核到的 live 症状不是单一故障，而是同一根问题的两种表现：

1. 直连 `http://127.0.0.1:9226` 时，shared-profile CDP context 有时直接报：
   - `TargetClosedError`
   - `connect ECONNREFUSED 127.0.0.1:9226`
2. 通过 driver 调 `gemini_web_self_check` 时，症状已从“快速 TargetClosedError”推进成“长等待/卡死型”，而不是立刻健康
3. 当前最新 send 侧真实 job 已经收口到：
   - [`artifacts/jobs/5b5f493c46a840feb1c55c2f70c3b824/result.json`](/vol1/1000/projects/ChatgptREST/artifacts/jobs/5b5f493c46a840feb1c55c2f70c3b824/result.json)
   - `status=error`
   - `phase=send`
   - `conversation_url=null`
   - `conversation_id=null`
   - `error_type=MaxAttemptsExceeded`
   - 根因文本仍指向 `UiTransientError: <TimeoutError: empty error>`

## 6. 当前判断

我当前的独立判断是：

1. 这批测试层修复是有效的：
   - self-check 恢复逻辑更接近真实现场
   - MCP transport gap 不再直接打断整条链
   - public session projection 更接近真实 send-phase repair 语义
2. 但 `W1` 仍没有过线。
3. 当前可以冻结的结论是：主剩余 failure surface 已集中到 Gemini live runtime/send path，而不是 public session ambiguity。
4. 但现有证据还不足以把根因进一步冻结成“shared-profile CDP runtime instability”这一句；`GEMINI_REUSE_EXISTING_CDP_PAGE=1` 也只能算运行时实验，不能当 authoritative 依据。
5. 因此下一批不该扩新 surface，而应继续只打：
   - live runtime/send path 稳态化
   - send cooldown churn 终态化
   - 真正的 terminal `completed` 证明

## 7. 下一步

下一步继续做：

1. 查 `9222 -> 9226` 之间的 runtime 实际角色与是否存在陈旧 forwarder/bridge
2. 明确 `GEMINI_REUSE_EXISTING_CDP_PAGE=1` 是否保留，避免让实验变量污染根因判断
3. 继续压缩 Gemini send-phase blank cooldown 的重试与等待窗口
4. 再跑真实 OpenClawBot live completion gate，直到拿到真实 `completed` 或更硬的 runtime 失败证据
