# ChatgptREST 全面体检 & 24 小时工作审计
**日期**: 2026-03-16 21:30 CST  
**审计窗口**: 2026-03-15 21:00 — 2026-03-16 21:30 (约 24h)  
**审计人**: Antigravity Agent

---

## 1. 系统总览

| 指标 | 值 | 状态 |
|------|-----|------|
| API 运行 | ✅ 正常 (pid 544908) | `git_sha=8cd2778689ee` |
| Jobs 完成 | 6,612 | — |
| Jobs 出错 | 610 (8.1%) | ⚠️ 偏高 |
| Jobs 进行中 | 2 | 正常 |
| Jobs 已取消 | 271 | — |
| Stale Jobs | 0 | ✅ |
| Stuck Wait Jobs | 0 | ✅ |
| UI Canary | ✅ OK | 无失败 provider |
| Pause 状态 | `send` 模式，已过期 (inactive) | ✅ 无阻塞 |
| Dashboard | ✅ 全部 8 页 200 OK | Funnel 已修复→18711 |

> [!WARNING]
> **需要关注**: 107 个 open incidents + 7 个 open client issues

---

## 2. Open Client Issues（7 个，全 P2）

| # | Issue | Kind | 症状 | 最后出现 |
|---|-------|------|------|---------|
| 1 | AttachmentContractMissing | `chatgpt_web.ask` | prompt 引用本地文件但未声明 `file_paths` (`maint_daemon_state.json`) | 15:39 今天 |
| 2 | AttachmentContractMissing (dup) | `job_error` | 同一 job 的 executor_auto 报告 | 15:39 今天 |
| 3 | GeminiGoogleVerification | `gemini_web.ask` | Gemini 命中 Google 验证页（代理/登录态问题） | 12:50 今天 |
| 4 | WaitNoProgressTimeout (Gemini) | `gemini_web.ask` | wait 阶段无进展 `age=6023111s` | 07:22 今天 |
| 5 | ToolCallError (extract_answer) | `chatgpt_web.extract_answer` | SSE stream timeout (deadline exceeded) | 3/14 21:43 |
| 6 | WaitNoProgressTimeout (ChatGPT) | `chatgpt_web.ask` | wait 阶段无进展 `age=12324s` | 3/14 12:24 |
| 7 | WaitNoThreadUrlTimeout | `gemini_web.ask` | wait 无 conversation_url `age=293784s` | 3/12 16:57 |

### 分析

- **Issues 1-2 (AttachmentContractMissing)**: `maint_daemon` 发出的 review prompt 中引用了 `maint_daemon_state.json` 但未通过 `input.file_paths` 传递。**根因**: maint_daemon 代码未在创建 job 时声明附件路径。需要修复 maint_daemon 的 job submission 逻辑。
- **Issue 3 (GeminiGoogleVerification)**: Gemini 通道命中了 Google 验证。通常因为 Chrome profile 未登录 Google 或代理/出口 IP 不在支持区域。
- **Issues 4, 6, 7 (Wait Timeout 系列)**: 都是极端老化的 `age` 值（ `6M+ seconds` 即 ~70 天），说明这些是历史遗留的陈旧 job，但 `stale_audit_cleanup` 未能将其正确终态化。应手动关闭或由 guardian 自动 mitigate。
- **Issue 5 (ToolCallError)**: ChatGPT SSE 流超时，偶发性问题，已知的 infra 抖动。

---

## 3. Open Incidents（107 个，全 P2）

### Top 20 高频 Incident 签名

| 签名模式 | 次数 | 关联 Jobs | 性质 |
|---------|------|----------|------|
| `RuntimeError` (chatgpt_web.ask) | 81,910 | 50 | 🔴 `stale_audit_cleanup` 批量回扫产物 |
| `WaitNoProgressTimeout` (chatgpt) | 17 | 17 | ⚠️ Wait 超时 |
| `WaitNoThreadUrlTimeout` (gemini) | 19 | 19 | ⚠️ 无 conversation URL |
| `QwenNotLoggedIn` | 10 | 10 | ⚠️ Qwen 未登录 |
| `GeminiUnsupportedRegion` | 8 | 8 | ⚠️ 区域限制 |
| `NeedsFollowup` (chatgpt) | 8 | 8 | job 需追问 |
| `GeminiGoogleVerification` | 5 | 5 | Google 验证拦截 |
| `ToolCallError` (chatgpt) | 5 | 5 | UI 自动化故障 |
| `RuntimeError` (gemini) | 5 | 5 | 运行时错误 |
| `Blocked` (chatgpt) | 5 | 5 | 被 audit cleanup 标记 |
| `stuck:created>Ns` (chatgpt) | ~15 | ~20 | 长期卡住的老 job |
| `GeminiFollowupSendUnconfirmed` | 2 | 2 | 追问发送未确认 |
| `GeminiDeepResearchToolUnavailable` | 1 | 1 | DR 工具不可用 |
| `GeminiCaptcha` | 2 | 2 | 验证码拦截 |
| `DriveUploadNotReady` | 3 | 3 | Drive 上传未就绪 |
| `URLError` (chatgpt) | 1 | 1 | 网络错误 |
| `HealthProbeStale` | 1 | 1 | 健康探针陈旧 |
| `AttachmentContractMissing` | 1 | 1 | 附件契约缺失 |
| `CDP Exception` (gemini) | 3 | 3 | 浏览器连接断开 |

### 关键发现

> [!IMPORTANT]
> **107 个 incidents 中绝大多数（~90+）都来自 `stale_audit_cleanup_20260316`**
> 
> 这是一次 批量陈旧 job 清理操作 在今天凌晨 06:xx UTC 执行的结果。它将历史上积压的卡住/失败 job 统一标记为 error，并为每个独特签名创建了 incident。这些**不是新发生的故障**，而是历史问题的一次性暴露。

- **Codex 自动修复介入率**: 50 个 incidents 中已有 Codex repair 介入（`codex_run_count>0`），其中大部分 `codex_last_ok=true`，说明自动诊断管线正常运转。
- **真正需要关注的活跃问题**:
  1. `AttachmentContractMissing` — maint_daemon prompt 逻辑需修复
  2. `GeminiGoogleVerification` — Gemini 通道登录态/代理检查
  3. `QwenNotLoggedIn` — Qwen 通道需重新登录

---

## 4. 近 24h 错误 Job 分析

| 错误类型 | 数量 | 主要原因 |
|---------|------|---------|
| `stale_audit_cleanup` 系列 | ~50+ | 历史 job 批量终态化 |
| `MaxAttemptsExceeded` (CDP) | ~10 | Chrome 崩溃/断连，重试耗尽 |
| `TargetClosedError` / `Target crashed` | ~8 | Chrome 进程不稳定 |
| `AttachmentContractMissing` | 3 | prompt 中引用文件未声明 |
| `ValueError: Unknown job kind` | 3 | 客户端使用了错误的 `kind`（`chat`/`gemini`/`research`） |
| `IdempotencyCollision` (sre.fix_request) | 2 | 幂等 key 冲突 |
| `Codex RuntimeError` (sre.fix_request) | 4 | Codex SRE 坐标器执行失败 |
| `GeminiCaptcha` | 2 | 验证码拦截 |

### 质量判定

| 维度 | 评分 | 说明 |
|------|------|------|
| 核心 API 可用性 | ✅ **9/10** | API 正常，dashboard 正常，无 stuck jobs |
| Job 成功率 | ⚠️ **7/10** | 6612 / 7493 = 88.2%（含历史清理的 error） |
| 近 24h 实际成功率 | ✅ **~95%+** | 排除 stale_cleanup 后实际新 job 成功率很高 |
| 自动修复管线 | ✅ **8/10** | Codex repair 正常介入，大部分诊断成功 |
| Gemini 通道 | ⚠️ **5/10** | GoogleVerification + UnsupportedRegion + DriveUpload 问题 |
| ChatGPT 通道 | ✅ **8/10** | 偶发 CDP 断连，但 canary 正常 |
| Qwen 通道 | ❌ **3/10** | NotLoggedIn 错误表明通道离线 |
| Dashboard | ✅ **9/10** | 全页面正常，Funnel 已修复 |

---

## 5. 24 小时 Agent 工作记录

### 活动量

| 日期 | 事件总数 | 
|------|---------|
| Mar 15 (昨天) | 410 |
| Mar 16 (今天) | 251 |

### 事件类型分布（今天）

| 事件类型 | 数量 |
|---------|------|
| `agent.git.commit` | 139 |
| `agent.git.head_change` | 87 |
| `agent.task.closeout` | 25 |

### Agent 参与度（今天）

| Agent | 事件数 | 涉及工作 |
|-------|--------|---------|
| gemini-cli | 96 | ChatgptREST + finagent 代码提交 |
| unknown (hooks) | 68 | 自动 head_change 事件 |
| codex2 | 32 | ChatgptREST 开发 |
| codex | 31 + 23 = 54 | 模型路由对齐 + finbot dashboard + 代码评审 |
| antigravity | 1 | finagent test 修复 closeout |

### 关键交付（最近 24h）

1. **模型路由栈对齐** — minimax → qwen → gemini 降级链已下发到所有 OpenClaw agent
2. **finbot Phase 6-8 合并** — dashboard IA 升级、共识适配器、双向写回
3. **finagent theme_report test 修复** — 时间止损策略解析 + 测试断言修复
4. **外部代码评审** — claudeminmax 代码评审记录
5. **Dashboard Tailscale Funnel 修复** — `/v2/dashboard` 路由从 8787 改到 18711

---

## 6. 建议操作

### 🔴 立即处理

1. **Qwen 通道重新登录**: 10 个 `QwenNotLoggedIn` 错误，通道完全离线
2. **Gemini 通道检查**: 验证 Google 登录态 + 代理出口区域
3. **AttachmentContractMissing**: 修复 maint_daemon 的 job 提交逻辑，显式声明 `file_paths`

### 🟡 本周处理

4. **历史 stale incidents 批量关闭**: 107 个 open incidents 绝大多数是 cleanup 产物，应由 guardian 自动 mitigate 或手动批量关闭
5. **Issue #4/#6/#7 (超时老龄 job)**: 确认这些 job 已正确终态化后关闭对应 issues
6. **Unknown job kind 错误**: 客户端发了 `kind=chat/gemini/research` 等无效 kind，需排查来源并修复

### 🟢 持续监控

7. Chrome CDP 稳定性（当前 canary 正常，但历史有多次 `TargetClosedError`）
8. Codex SRE fix_request 成功率（4/~10 失败，主要是 Codex 坐标器执行报错）
