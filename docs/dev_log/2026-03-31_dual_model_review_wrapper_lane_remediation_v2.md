# 2026-03-31 Dual-Model Review Wrapper Lane Remediation v2

## 状态

`v1` 的结论仍成立，但现在需要补两条更精确的运行面结论：

1. `GeminiImportCodeUnavailable` 那条 fail-open 修复已经在主仓代码里。
2. `ChatGPT Pro` review lane 当前剩余的主要不稳定面，不再是“找不到 prompt box 就一刀切 blocked”，而是：
   - Linux `9226` lane 上会短时命中 Cloudflare / verification 页面。
   - auto-click 后经常进入 “verification in progress” 的中间态，而不是立即 resolved 或 hard-fail。

这轮新增修复的目标，就是把这个中间态显式建模，而不是继续把它误报成普通 blocked。

## 新增根因判断

### 1. ChatGPT review lane 的真实剩余问题

之前的 fresh-tab / prompt selector 问题修掉后，wrapper lane 仍会在 CDP open 阶段撞到：

- `Just a moment...`
- turnstile / challenge 页面
- auto-click 后页面文案进入：
  - `Verification successful. Waiting for chatgpt.com to respond`
  - `loading-verifying`
  - `Verifying...`

这类状态不是“已恢复”，也不是“必须人工马上接管”的最终 blocked。它更像：

- verification 已经被触发
- challenge 正在自行收尾
- 此时继续把 job 终态化成 hard blocked，会把 wrapper lane 推向错误分支

### 2. Linux 9226 vs Windows 19222 的运行面对照

为了避免继续误判，我做了两条 lane 的独立核验：

#### Windows 19222

- 通过 Windows reverse tunnel 建立了 Linux 本地 `127.0.0.1:19222 -> Windows 127.0.0.1:9222` 的 SSH local forward。
- `http://127.0.0.1:19222/json/version` 返回：
  - Windows Chrome/146
  - 有 `webSocketDebuggerUrl`
- `chatgpt_web_self_check` 在这条 lane 上能通过，说明 Cloudflare/fresh-tab 不是主阻断。
- 但 `chatgpt_web_capture_ui` 报：
  - `ChatGPT appears to require login or re-authentication`

结论：
- 19222 是有效的 Windows user-browser CDP lane
- 但当前未登录 ChatGPT，不适合作为 review 主执行 lane

#### Linux 9226

- `http://127.0.0.1:9226/json/list` 仍能看到 ChatGPT 会话页
- `chatgpt_web_self_check` 在 `9226` 上现在可成功返回：
  - `ok=true`
  - `status=completed`
  - `title=ChatGPT`
  - `model_text=ChatGPT`

结论：
- 当前真正可用的 review 主 lane 仍是 Linux `9226`
- 剩余问题不是“完全不可用”，而是 verification 中间态建模不够细

## 代码改动

文件：

- `chatgpt_web_mcp/_tools_impl.py`
- `tests/test_chatgpt_cdp_page_reuse.py`

### 1. blocked state 分类补充

把 `verification_pending` 纳入 cooldown 类 blocked state，而不是和 hard blocked 混为一类：

- `_blocked_status_from_state()`
- `_chatgpt_action_allowed_during_blocked()`

这样：

- `wait`
- `conversation_export`

在 verification 正在收尾时仍可继续走恢复路径。

### 2. verification pending 冷却窗口

新增：

- `_chatgpt_verification_pending_cooldown_seconds()`

默认 90s，显式区别于更长的 hard verification cooldown。

### 3. auto-verification 观察窗口

新增：

- `_chatgpt_auto_verification_observe_seconds()`
- `_chatgpt_auto_verification_poll_ms()`
- `_chatgpt_verification_pending_signals()`

行为变化：

- auto-click 后不再只做一次 post-check
- 会在短观察窗口内轮询页面
- 若发现：
  - `Verification successful. Waiting for chatgpt.com to respond`
  - `loading-verifying`
  - `Verifying...`
- 就把结果标成：
  - `pending=true`
  - `pending_signals=[...]`

### 4. blocked reason 从 `verification/cloudflare` 分裂出 `verification_pending`

在 `_raise_if_chatgpt_blocked()` 中：

- 若 auto-click 后是 pending 中间态：
  - `reason=verification_pending`
  - cooldown 用短窗口
  - 错误消息改成“verification appears to be in progress”
- 若仍是硬 challenge：
  - 保持 `verification` / `cloudflare`

## 测试

新增/更新：

- `tests/test_chatgpt_cdp_page_reuse.py`

补的回归点：

1. hidden turnstile fallback 点击坐标
2. `verification_success_waiting` / `loading-verifying` 被识别成 pending signal
3. `_raise_if_chatgpt_blocked()` 在 pending 情况下写入：
   - `reason=verification_pending`
   - cooldown 走 pending 冷却窗口
4. `_blocked_status_from_state()` 把 `verification_pending` 映射成 `cooldown`

实际通过：

```bash
cd /vol1/1000/projects/ChatgptREST && python3 -m py_compile \
  chatgpt_web_mcp/_tools_impl.py \
  tests/test_chatgpt_cdp_page_reuse.py
```

```bash
cd /vol1/1000/projects/ChatgptREST && ./.venv/bin/pytest -q \
  tests/test_chatgpt_cdp_page_reuse.py \
  -k 'turnstile or blocked or self_check or verification_pending'
```

结果：

- `7 passed`

## 运行面验证

### Windows 19222 lane

验证点：

- `http://127.0.0.1:19222/json/version`
  - 返回 Windows Chrome
  - `webSocketDebuggerUrl=true`
- `chatgpt_web_self_check`：
  - 可通过
- `chatgpt_web_capture_ui`：
  - 返回 `auth` blocked

结论：

- lane 可达
- 但当前没有 ChatGPT 登录态

### Linux 9226 lane

验证点：

- `http://127.0.0.1:9226/json/list` 可见现有 ChatGPT 会话
- `chatgpt_web_self_check` 现已恢复成功

结论：

- wrapper lane 当前应继续以 `9226` 作为主执行 lane
- `19222` 可保留为后续可切换的 user-browser candidate lane，但不是当前默认值

## 对 review workflow 的实际意义

这轮修复后，ChatGPT Pro wrapped review lane 的语义不再是：

- 找不到 prompt -> hard fail

而是：

- verification in progress -> cooldown / resumable / recoverable

这让后续：

- `advisor_agent_wait`
- `result`
- `authoritative answer recovery`

可以继续走服务内恢复链，而不是逼着操作者跳到人工浏览器路径。

## 边界

这轮没有做：

- Windows 19222 lane 的 ChatGPT 登录自动化
- review repo workflow 结构改造
- public advisor-agent clarify gate 策略改造
- ChatGPT Web 外部平台级风险完全消除

这轮只做：

- 把 verification 中间态从“误报 hard blocked”修成“可恢复 cooldown”
- 明确当前主执行 lane 仍是 Linux `9226`

## 结论

`v2` 相比 `v1` 的关键增量不是更多 workaround，而是把 ChatGPT review lane 的真实运行状态建模补完整了：

- `Windows 19222`：可达但未登录
- `Linux 9226`：已登录且 wrapper 自检恢复成功
- verification 中间态：现在被显式建成 `verification_pending`

这使得后续必须通过封装 lane 拿正式长答案的任务，可以继续在服务设计内推进，而不是被迫回到人工浏览器操作。
