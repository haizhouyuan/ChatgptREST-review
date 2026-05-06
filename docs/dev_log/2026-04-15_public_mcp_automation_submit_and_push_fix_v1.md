# 2026-04-15 public MCP automation submit and push fix v1

## 背景

`Hermes` workbench 已经切到 `automation-kernel-v1` public MCP surface，但真实 submit-path 仍有两类故障：

1. `automation_ask` / `automation_job_create` 会在 low-level submit guard 处失败
2. `automation_ask` 即使 `auto_wait=true` 也只返回 `foreground_wait`，没有进入 push 语义

这次修复的目标不是再给旧 facade 打补丁，而是把 public MCP 作为共享 automation kernel 的真实提交口修到可用。

## 根因一：public MCP 复用 low-level submit 时，身份与 allowlist 不一致

### 现象

- `automation_ask` 出现 `low_level_ask_client_identity_mismatch`
- `automation_job_create(kind=gemini_web.generate_image)` 出现 `ClientNotAllowed`
- `automation_job_cancel` 在 public MCP 下被 `CancelClientNotAllowed` 拦截

### 根因

public MCP 的 northbound identity 是 `chatgptrest-agent-mcp`，但 low-level submit guard 只接受注册过的 submit wrapper 身份。  
直接让 public MCP 身份进入 low-level submit，会同时触发：

- body `client.name` 与 header `X-Client-Name` 不一致
- coarse allowlist 不允许 `gemini_web.generate_image`
- cancel allowlist 未包含 public MCP 身份

### 修复

1. public MCP 不再伪装成 low-level caller，本体仍维持 `chatgptrest-agent-mcp`
2. 真正下钻到 `/v1/jobs` 时，按 `kind` 自动投影到注册过的 internal submit wrapper：
   - `chatgpt_web.ask -> chatgptrest_chatgpt_ask_submit`
   - `gemini_web.ask -> chatgptrest_gemini_ask_submit`
   - `qwen_web.ask -> chatgptrest_qwen_ask_submit`
   - `gemini_web.generate_image -> chatgptrest_gemini_generate_image_submit`
3. `ask_client_registry.json` 扩充 generate-image alias 与 allowlist
4. `routes_jobs.py` 的 coarse allowlist gate 对注册的 generate-image submit 也放行
5. runtime contract 增加 public MCP cancel allowlist 检查，启动即 fail-closed

## 根因二：public MCP 本来是 sessionful，但 background wait 仍误走 generic stateless 默认值

### 现象

真实 `automation_ask(auto_wait=true)` submit 成功后，只返回：

- `completion_mode = foreground_wait`
- `push_enabled = false`

而不是预期的：

- `completion_mode = push`
- `background_wait_started = true`

### 第一层问题

`_background_wait_start(...)` 已经改成支持 `cfg=BackgroundWaitConfig(...)` 调用，但函数签名里的 flat kwargs 之前没有默认值。  
public MCP 调用时只传 `job_id + cfg + ctx`，会在 Python 绑定阶段直接抛 `TypeError`。  
这个异常又被上层 `except Exception: pass` 吃掉，导致 background wait 静默失效。

这层已经在本次提交里补齐：

- flat kwargs 全部给默认值
- `cfg` 存在时统一覆盖 flat 参数

### 第二层问题

修完签名后，background wait 仍失败。真正原因是：

- generic `chatgptrest.mcp.server` 的 `_fastmcp_stateless_http_default()` 默认返回 `True`
- public agent MCP 运行在独立的 sessionful service 上，但复用 job-kernel helper 时，background wait 仍检查的是 generic 默认值
- 结果是 public MCP 明明是 sessionful，background wait 却被误判成 `BackgroundWaitUnsupported`

### 修复

在 `chatgptrest/mcp/server.py` 中把两个概念拆开：

1. `FastMCP` 本体默认值仍由 `_fastmcp_stateless_http_default()` 管理  
   这保留了 generic server 的历史语义
2. background wait 单独使用 `_background_wait_stateless_http_default()`  
   规则是：
   - 如果显式设置 `FASTMCP_STATELESS_HTTP`，一律尊重
   - 否则如果当前运行身份是 public agent MCP：
     - 读取 `CHATGPTREST_AGENT_MCP_STATELESS_HTTP`
     - 未设置时默认 **stateful**
   - 其他 server 仍保持默认 stateless

这样 generic MCP 与 public agent MCP 的默认值不会再互相污染。

## 测试

Focused tests：

```bash
.venv/bin/python -m pytest -q \
  tests/test_mcp_stateless_mode.py \
  tests/test_mcp_unified_ask_min_chars.py \
  tests/test_agent_mcp.py \
  tests/test_jobs_write_guards.py \
  tests/test_mcp_trace_headers.py \
  tests/test_mcp_gemini_ask_submit.py \
  tests/test_mcp_server_entrypoints.py
```

通过。

新增/增强覆盖点包括：

- public agent client 默认 background-wait 为 stateful
- `CHATGPTREST_AGENT_MCP_STATELESS_HTTP=1` 可显式退回 stateless
- `_background_wait_start` 可只用 `cfg` 调用
- generate-image submit 可绕过 coarse allowlist
- public MCP runtime contract 现在会检查 cancel allowlist

## Live smoke

真实 sessionful MCP smoke 证据：

- `/tmp/chatgptrest-automation-live-smoke.json`

关键结果：

- `automation_ask.ok = true`
- `automation_ask.completion_mode = push`
- `automation_ask.push_enabled = true`
- `automation_ask.background_wait_started = true`
- `automation_ask.next_action.kind = await_push`
- `automation_job_cancel.ok = true`
- `automation_job_create(kind=gemini_web.generate_image).ok = true`
- `automation_job_cancel_generate_image.ok = true`

这证明：

1. public MCP 现在可以稳定 submit ask / generate-image
2. cancel lane 已对 public MCP 开放
3. push receipt 语义已经真正生效，不再退回 foreground wait

## 结论

这次修复完成后，`automation-kernel-v1` public MCP 已具备：

- northbound public identity 与 low-level submit identity 解耦
- generate-image 与 ask 共用统一 submit guard 逻辑
- sessionful public MCP 默认启用 push background wait
- submit / cancel / push receipt 三条主路径都已通过 live smoke

下一步不再需要继续扩 MCP 本体，重点应回到：

- `Hermes` workbench 对接这条稳定的 automation push contract
- 让前台只提交 receipt，不再做 foreground wait
