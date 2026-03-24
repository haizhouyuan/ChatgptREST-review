#!/usr/bin/env markdown
# ChatgptREST 智能 SRE 落地架构方案（Codex SDK/CLI）

目标：把“监控/诊断/修复”做成**可观测、可控、可回滚**的闭环，优先解决以下两类高频事故：

- **登录态/风控导致 blocked**：Chrome/CDP 活着但 ChatGPT 退出登录或 Cloudflare challenge，导致 worker 反复 requeue、白白消耗等待与干扰排障。
- **Pro Thinking 被跳过/过短**：出现 `Skipping` 或 `Thought for < 5min`（或误点 `Answer now`）导致回复质量明显下降。

本方案强调：**Codex SDK/CLI 用于“诊断决策层”，ChatgptREST/driver 负责“证据与动作执行层”。**

## 0) 强约束（必须遵守）

- **不做任何 ChatGPT Web 发问类测试**（包含 smoke test prompt）。只允许：状态探针、抓证据、refresh/regenerate（无新 user prompt）。
- **不修改 ChatGPT 发送节流 61 秒**（driver 的 `CHATGPT_MIN_PROMPT_INTERVAL_SECONDS=61` 保持不变）。
- **blocked/challenge fail-closed**：发现登录页/验证页 → 只收证据并保护性暂停，避免“越试越封”。
- **自动动作分级启用**：按 `docs/ops_rollout_plan_p0p1p2_safe_enable_20251228.md`，先合入观测(P0)→再启用修复(P1/P2)。

## 1) P0：可观测（监控 → 证据落盘）

### 1.1 信号源

- **Driver blocked 状态**：`state/driver/chatgpt_blocked_state.json`（或 `CHATGPT_BLOCKED_STATE_FILE`）
- **浏览器网络日志（可滚动删除）**：`CHATGPT_NETLOG_ENABLED=1` 时写入 `artifacts/chatgpt_web_netlog.jsonl*`（Rotating）
- **Thinking observation（不含思维链）**：driver 在工具结果里 best-effort 附带 `thinking_observation`：
  - `thought_seconds` / `thought_too_short`（阈值由 `CHATGPT_THOUGHT_GUARD_MIN_SECONDS` 控制，默认 300）
  - `skipping` / `answer_now_visible`
  - `answer_now_blocked_clicks`（若误点被拦截会计数，并打印 console：`[chatgptrest] blocked Answer now click`，可在 netlog 中定位）
- **异常快照扩展（按需）**：`CHATGPT_THOUGHT_GUARD_CAPTURE_DEBUG=1` 时，遇到异常信号会附带 `thought_guard_debug_artifacts`（png/html/txt）

### 1.2 事件落盘（可检索）

- worker 会把异常标记写入 events：
  - `thought_guard_abnormal`
  - `thought_guard_regenerated`
- 这些事件会同时写入 DB 与 `artifacts/jobs/<job_id>/events.jsonl`，便于回放。

## 2) P0：快速诊断入口（repair.check）

新增 `kind=repair.check`（**不发送 prompt**）用于一键拉齐诊断信息：

- DB 概览（排队/错误/blocked 近况）
- blocked_state（本地文件）
- CDP 探针（`/json/version`）
- driver probe（best-effort：`blocked_status` / `rate_limit_status` / `tab_stats`，可选 `self_check`/`capture_ui`）
- 产物：
  - 人类可读：`artifacts/jobs/<job_id>/answer.md`
  - 机器可读：`artifacts/jobs/<job_id>/repair_report.json`

推荐跑一个专用 repair worker，避免被 send 节流/队列拖慢：

```bash
cd /vol1/1000/projects/ChatgptREST
ops/start_worker.sh all repair.
```

## 3) P1：Codex 诊断决策层（读证据 → 给动作建议）

Codex SDK/CLI 的定位：**从事故包/证据中归纳根因假设 + 给出“安全动作计划”**，而不是直接去“自动发问/自动改生产”。

### 3.1 输入（证据包）

来源建议：
- `ops/maint_daemon.py` 生成的 incident evidence pack（`artifacts/monitor/maint_daemon/incidents/<incident_id>/`）
- 或者直接用 `repair.check` 的 job artifacts

### 3.2 结构化输出（JSON Schema）

本仓库提供：
- Schema：`ops/schemas/codex_sre_actions.schema.json`
- 分析脚本（read-only）：`ops/codex_sre_analyze_incident.py`

用法：

```bash
ops/codex_sre_analyze_incident.py artifacts/monitor/maint_daemon/incidents/<incident_id>
```

输出：默认写到 `.../<incident_id>/codex/sre_actions.json`。

> 该脚本使用 `codex exec --sandbox read-only --output-schema ...`，硬约束已写入 prompt：不做 smoke test、不改 61s、优先只读、动作需 guardrails。

## 4) P1/P2：动作执行层（有限白名单 + 护栏）

允许的动作（建议白名单）：

- 只读/证据：`capture_ui`、启用/停用 netlog（通过 env + driver 重启）
- 低风险 UI 动作（仍属副作用，需护栏）：
  - `chatgpt_web_refresh`：刷新页面（无 prompt）
  - `chatgpt_web_regenerate`：点击“重新生成/Regenerate”（无新 user prompt）
- blocked 恢复后的清理：`chatgpt_web_clear_blocked`
- 进程级：`restart_chrome` / `restart_driver`（限次、冷却、失败熔断）

护栏要点：
- regenerate：`CHATGPT_REGENERATE_STATE_FILE` + `CHATGPT_REGENERATE_MIN_INTERVAL_SECONDS`（默认 1800s）+ `CHATGPT_REGENERATE_MAX_PER_WINDOW`/`CHATGPT_REGENERATE_WINDOW_SECONDS`
- refresh（wait 内自动 refresh）：`CHATGPT_WAIT_REFRESH_STATE_FILE` + `CHATGPT_WAIT_REFRESH_MIN_INTERVAL_SECONDS` + `CHATGPT_WAIT_REFRESH_MAX_PER_WINDOW`/`CHATGPT_WAIT_REFRESH_WINDOW_SECONDS`
- blocked/challenge：只做证据采集，进入保护性暂停，等待人工登录/验证

## 5) “Thought for < 5min” 质量守护（无 prompt）

当前落地机制：
- driver 工具结果附带 `thinking_observation`（best-effort）
- executor 在 `preset=pro_extended` 且非 `deep_research` 时做校核：
  - `Thought for < CHATGPTREST_THOUGHT_GUARD_MIN_SECONDS` 或 `skipping/answer_now_visible` → 标记异常
  - 可选：`CHATGPTREST_THOUGHT_GUARD_AUTO_REGENERATE=1` 时触发一次 `chatgpt_web_regenerate`（仍受 regenerate 护栏约束）

风险提示（需要你明确接受后再开自动修复）：
- regenerate 属 UI 副作用动作，过度使用可能提高风控风险或造成 UI 状态机异常。
- “思考时长短”并不总是错误：可能是后端路由/缓存/模型策略变化导致；因此建议先 P0 观测，再逐步开启 P1 自动 regenerate。

## 6) 建议上线顺序（最小风险）

1. 合入 P0：观测 + 证据（thinking_observation / netlog / repair.check），默认不自动修复
2. 观测 24–72h：验证误报率、对 blocked 的熔断是否符合预期
3. 小流量启用：
   - `CHATGPT_THOUGHT_GUARD_CAPTURE_DEBUG=1`（只在需要时）
   - `CHATGPTREST_THOUGHT_GUARD_AUTO_REGENERATE=1`（只对 pro_extended，且已有 regenerate state file）
4. 扩大范围前：把 guardrails 参数固化到 `ops/start_driver.sh`/部署环境，避免“默认开火”
