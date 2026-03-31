# 2026-03-31 Wrapped Review Wait Transport Recovery Fix v1

## 背景

双模型评审的封装 lane 已经修过两轮：

1. `adbc8da`：恢复 packaged dual-model review 主链
2. `c2bc0ea`：让 wrapped ChatGPT Pro 评审在有 thread URL 时优先回到 thread，而不是刷新根页触发 Cloudflare

第二轮之后，ChatGPT Pro 的 wrapper lane 仍存在一条剩余根因：

- `advisor_agent_turn` 已经成功提交 review 任务
- `advisor_agent_wait` 在 streamable-HTTP MCP 长连接等待期间收到大量 SSE ping
- 连接在没有完整 JSON 结果体的时刻断开，wrapper 直接抛出 `IncompleteRead`
- 结果是 review lane 被错误判成失败，而不是继续用同一个 `session_id` 恢复等待

## 根因

`skills-src/chatgptrest-call/scripts/chatgptrest_call.py` 之前的实现有两个缺口：

1. `_jsonrpc_call()` 对 `http.client.IncompleteRead` 没有做 partial body 解析
2. agent mode 在 `advisor_agent_wait` 失败后没有恢复策略，只会直接退出

这和当前 public advisor-agent MCP 的真实运行方式不匹配：

- long-running review/research 使用 `delivery_mode=deferred`
- wrapper 会先提交 `advisor_agent_turn`
- 然后通过 `advisor_agent_wait(session_id, timeout_seconds)` 等待终态
- `advisor_agent_wait` 走 streamable-HTTP / SSE keepalive，允许中途出现 ping

所以 wrapper 必须把 “wait transport 失败” 和 “远端 session 真失败” 区分开。

## 修复

### 1. partial SSE 解析

`_jsonrpc_call()` 现在在 `resp.read()` 抛出 `IncompleteRead` 时：

- 先提取 `exc.partial`
- 尝试按 JSON-RPC / SSE body 解析
- 如果 partial 中已经包含最终 `data: {...}`，则直接恢复并返回

### 2. wait transport recovery

新增 `_run_agent_wait_with_recovery()`：

- 第一优先：正常调用 `advisor_agent_wait`
- 如果出现 `IncompleteRead` / transport-like wait failure：
  - 用同一 `session_id` 调 `advisor_agent_status`
  - 如果 status 已终态，直接返回 status 结果
  - 如果 status 仍在运行，按剩余预算重试 `advisor_agent_wait`
- 恢复成功后，结果里会带：
  - `wait_transport_recovered=true`
  - `wait_transport_retry_count=<n>`

### 3. SSE 解析更稳

`_decode_sse_json()` 现在会：

- 忽略 `: ping ...`
- 忽略空 `data:` / `[DONE]`
- 优先取最后一个可解析的 JSON event

## 回归

新增两类测试：

1. `test_jsonrpc_call_decodes_partial_sse_payload_from_incomplete_read`
   - 覆盖 partial SSE 内已经有最终 JSON event 的恢复场景

2. `test_skill_main_agent_mode_wait_transport_retries_after_incomplete_read`
   - 覆盖 `advisor_agent_wait` 第一次 `IncompleteRead`
   - wrapper 改走 `advisor_agent_status`
   - 然后第二次 `advisor_agent_wait` 成功收口

## 预期效果

这次修复之后，packaged review workflow 对长评审的等待阶段不再因为一次 streamable-HTTP 断连就整体失败。

正确语义变成：

- `advisor_agent_turn` 已提交
- `advisor_agent_wait` transport 出错
- wrapper 继续围绕同一 `session_id` 恢复，而不是要求外部人工切浏览器/重发问题

## 边界

这次修的是 wrapper wait transport 恢复，不代表：

- 外部平台不会再出现 Cloudflare
- 所有长连接都不会再断

但它保证了：

- **封装 lane 会优先走服务内恢复**
- **不会因为单次 wait transport 断连就放弃正式长答**
