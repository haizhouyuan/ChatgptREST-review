# Repair Agent Playbook

适用范围：`kind=repair.autofix`（以及 maint_daemon 的 Codex autofix 执行动作）。

目标：在**不发送新 prompt**的前提下，把已有 ask job 从 `cooldown/blocked/needs_followup` 拉回 `completed`，并留下可审计证据。

备注：maint_daemon 的 `codex maint fallback` 会在 incident 级别自动提交 `repair.autofix`，同样遵守本 playbook 的硬约束与动作顺序。

## 0. 硬约束（必须遵守）

- 禁止发送新问题：不得创建新的 `chatgpt_web.ask/gemini_web.ask/qwen_web.ask` 作为“测试”。
- 仅处理目标作业：围绕 `target_job_id` 与其 `conversation_url` 操作，不扩大影响面。
- 重启动作必须受护栏：若存在任意非 repair 作业处于 `phase=send`，禁止 `restart_driver/restart_chrome`。
- systemd 管理场景下，`restart_driver` 失败后**禁止**退回脚本直启（避免产生 orphan 进程占住 singleton lock）。
- 不得直接把 `auth/verification` 判定为“需要人工登录”：
  - 先验证 `CHATGPT_CDP_URL` 是否真的是 DevTools 端点（`/json/version` 且含 `webSocketDebuggerUrl`）；
  - 再尝试自动恢复（`clear_blocked` + `self_check` + 验证页自动点选）；
  - 自动恢复失败后，才输出人工步骤。
- 每次动作都要可追溯：写入 `repair_autofix_report.json`，并在原 job 事件里保留关联。

## 1. 权限分级（默认）

- `low`：`capture_ui`, `refresh`, `regenerate`, `clear_blocked`
- `medium`：`restart_driver`, `restart_chrome`
- `high`：默认禁止自动执行

执行时同时满足：
- 在 `allow_actions` 白名单内；
- 动作 `risk <= max_risk`；
- 通过 send-phase 护栏（对重启类动作）。

## 2. 标准处置顺序（先低风险后中风险）

1. 读取现场
- 查 `target_job` 当前 `status/phase/reason_type/reason`。
- 查 `run_meta.json` 与 `events.jsonl`（最近窗口）。
- 查 driver probe（`blocked_status/rate_limit_status/self_check/tab_stats`）。
- 对 `CHATGPT_CDP_URL` 做端点验真（避免“连到了非 Chrome 端口”）：
  - `curl --noproxy '*' http://127.0.0.1:<port>/json/version`
  - 必须返回 JSON 且包含 `webSocketDebuggerUrl`。

2. 低风险恢复
- `capture_ui`：先固定证据快照。
- `clear_blocked`：先清理可能陈旧的 blocked 状态。
- `self_check`：在同一 driver CDP Chrome 里复测会话可用性。
- `refresh`（ChatGPT）或 `regenerate`（ChatGPT）：尝试恢复渲染/收口，不发新 prompt。
- 若命中验证页：触发自动点选（driver 内置自动尝试），再二次 `self_check`。

3. 中风险恢复（仅在低风险失败后）
- `restart_driver`：优先动作，复位 MCP/CDP 会话。
- `restart_chrome`：仅当 driver 重启仍失败且 CDP 异常时执行。

4. 收口
- 若 job 已有 `conversation_url`，优先复用原会话继续 `wait/export`，避免重提问。
- 若仍失败，返回 `manual-required` 结论与下一步建议（登录验证/网络节点/代理策略）。

## 3. 状态到动作建议（推荐）

- `blocked`：
  - 先验真 CDP 端点，再 `capture_ui`，然后 `clear_blocked + self_check`，最后才考虑重启。
- `cooldown + InfraError/UiTransientError`：
  - 先 `capture_ui`，再 `restart_driver`，必要时 `restart_chrome`。
- `needs_followup + WaitNoProgressTimeout/WaitNoThreadUrlTimeout`：
  - 先 `capture_ui`；
  - ChatGPT 可尝试 `refresh`；
  - 若仍失败，`restart_driver`（受护栏）。

### 3.1 故障类别模板（Repair Agent 执行口径）

- `R1 服务不可达`（`Connection refused` / 端口不通）：
  - 只做服务恢复与健康验证，不改 prompt、不改业务入参。
- `R2 MCP 握手失败`（`Unexpected content type: None` / singleton lock）：
  - 优先 systemd 路径恢复；禁止脚本直启绕过 systemd。
- `R3 wait 收口失败`（网页已出答案但 job 不完成）：
  - 只围绕原 job 后台收口（wait/export/autofix），禁止新建 ask。
- `R4 上传粘滞失败`（`TargetClosedError + set_input_files`）：
  - 若已出现 `max_attempts_extension_skipped` 或同类错误重复，停止“继续拉高 max_attempts”，直接给出 `manual-required`（附 Drive 上传/路径修正建议）。
- `R5 Gemini 模式漂移`（tool selected state 识别不稳定）：
  - 先用多信号状态探测再切换，避免“切换成功但判定失败”误报。

### 3.2 等待策略（强制）

- Repair Agent 不得前台长时间 `job_wait` 阻塞执行线程。
- 必须采用后台等待/轮询（或短切片轮询），并在等待间隙继续做诊断与修复动作。
- 若等待超过窗口且无新事件，必须升级为“有动作的诊断”（driver/self_check/restart）或明确人工接管条件，不能无限空转。

## 4. 禁止事项

- 禁止“发一条 OK 测试”探活。
- 禁止在 `send` 有活跃作业时重启 driver/chrome。
- 禁止无证据直接宣告“已修复”。

## 5. 验收标准

- 目标 job 进入 `completed`，且 `answer_path` 可读；
- 或明确输出 `manual-required`（含原因、证据路径、人工步骤）。
