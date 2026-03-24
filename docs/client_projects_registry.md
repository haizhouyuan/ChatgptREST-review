# 客户端项目登记簿（ChatgptREST）

目标：明确“哪些客户端项目依赖 ChatgptREST”，并把 **用法文档** 与 **问题清单** 对齐，避免：

- 客户端 coding agent 误改 ChatgptREST 代码（引发风控/回归/不可控部署）
- ChatgptREST 更新后客户端文档漂移（导致误用/重复踩坑）

## 统一入口与版本基线

- Runbook 入口：`/vol1/1000/projects/ChatgptREST/docs/runbook.md`
- Fresh Codex 入口：`/vol1/1000/projects/ChatgptREST/docs/codex_fresh_client_quickstart.md`
- REST 契约：`/vol1/1000/projects/ChatgptREST/docs/contract_v1.md`
- 当前维护基线：`d0536d7`（2026-02-21）
- 运行版本自检：`curl -fsS http://127.0.0.1:18711/v1/ops/status | jq '.build'`
- 客户端文档同步状态（2026-02-21）：`planning/codexread/storyplay/homeagent/finchat/research/openclaw/maint(sim-dev)` 的 `docs/chatgptREST*.md` 与 `AGENTS.md` 已同步该基线信息。

## 强约束（必须遵守）

- 客户端项目的 coding agent **不允许修改** `projects/ChatgptREST` 的任何代码/配置/脚本。
- 遇到使用问题：必须在各自项目的 **问题清单文档** 里登记（见下表），并附上证据路径（`job_id` + `artifacts/jobs/<job_id>/...`）。

## 登记表

| Project | Path | 用法文档 | 问题清单 | 备注 |
|---|---|---|---|---|
| planning | `/vol1/1000/projects/planning` | `docs/chatgptREST.md` | `docs/chatgptREST_issues.md` | 规划/PPT 评审、材料提炼 |
| codexread | `/vol1/1000/projects/codexread` | `docs/chatgptREST.md` | `docs/chatgptREST_issues.md` | 多工具编排；强约束不改 ChatgptREST |
| storyplay | `/vol1/1000/projects/storyplay` | `docs/misc/chatgptREST.md` | `docs/chatgptREST_issues.md` | UI/代码评审、Gemini 生图封面/插图 |
| homeagent | `/vol1/1000/projects/homeagent` | `docs/chatgptREST.md` | `docs/chatgptREST_issues.md` | 代码评审与长答落盘 |
| finchat | `/vol1/1000/projects/finchat` | `docs/chatgptREST.md` | `docs/chatgptREST_issues.md` | MVP；补齐接入规范 |
| research | `/vol1/1000/projects/research` | `docs/chatgptREST.md` | `docs/chatgptREST_issues.md` | 研调/资料消化与证据链整理 |
| openclaw | `/vol1/1000/projects/openclaw` | `docs/chatgptREST.md` | `docs/chatgptREST_issues.md` | agent 托管/会话编排；仅通过 ChatgptREST 调用 Web ask |
| maint(sim-dev) | `/vol1/1000/projects/maint/openclaw/sim-dev` | `docs/chatgptREST.md` | `docs/chatgptREST_issues.md` | 运维演练沙箱；用于验证调用链与文档流程 |

## 维护流程（ChatgptREST 侧）

当你在 ChatgptREST 做了“对客户端有影响的改动”，按顺序执行：

1) 更新本仓库对外契约：`docs/contract_v1.md`
2) 更新本登记簿（如新增/迁移/删项目）：`docs/client_projects_registry.md`
3) 按登记表逐个同步客户端项目文档（至少更新两处）：
   - 该项目的用法文档（例如 `docs/chatgptREST.md`）
   - 该项目的 `AGENTS.md`（边界/禁止修改/问题登记）
4) 如改动涉及新错误/新状态/新自愈：补充到该项目的问题清单模板（字段/证据项）
5) 跑一次冷客户端验收：
   - `cd /vol1/1000/projects/ChatgptREST && PYTHONPATH=. ./.venv/bin/python ops/codex_cold_client_smoke.py --provider gemini --preset pro --profile cold-client-executor --question "请用两句话解释为什么写自动化测试可以降低回归风险。"`
   - 目标不是维护者自测，而是验证“一个没有本次上下文背景的 Codex 客户端”能否只靠仓库入口文档跑通链路。
   - 产物目录：`artifacts/cold_client_smoke/<timestamp>/`
   - 建议把 `scout / executor / judge` 拆成三种语义角色，不要让一个万能代理同时做发现、执行、判卷。
   - `executor` 应该显式记录自己的 `profile` / `model`；这两个字段是复现实验的重要条件，不应依赖默认 shell 状态。
   - 如果 sandboxed Codex shell 无法直连 `127.0.0.1:18711`，允许使用仓库已登记的 ChatgptREST MCP fallback，但必须把 transport gap 写进结果。
   - 若 cold client 只有在人工补提示后才能成功，视为客户端集成仍不合格。

Issue 闭环口径（统一）：
- “自动化”指：
  - 自动登记（worker_auto）
  - 自动修复尝试（repair.autofix）
  - guardian TTL 自动收口到 `mitigated`
  - guardian 对 `mitigated` issue 做第二阶段自动结案：
    - mitigated 之后
    - 同客户端 / 同 `kind`
    - 至少 `3` 次 qualifying success
    - 且无 recurrence
    - 自动更新为 `closed`
- `mitigated` 的口径：
  - live 验证已通过
- `closed` 的口径：
  - `mitigated` 后已经被真实客户端成功穿透验证，不再只是维护者自测通过

## 能力变更记录

- 2026-02-24: 写路径追踪门禁 + 取消归因硬化（可选强制）：
  - 新增可选门禁：`CHATGPTREST_REQUIRE_TRACE_HEADERS_FOR_WRITE=1` 时，`POST /v1/jobs` 与 `/cancel` 必须带 `X-Client-Instance` + `X-Request-ID`，否则 `400 missing_trace_headers`。
  - 新增可选门禁：`CHATGPTREST_REQUIRE_CANCEL_REASON=1` 时，`/cancel` 必须带 `X-Cancel-Reason`（或 `?reason=`），否则 `400 missing_cancel_reason`。
  - MCP/CLI 已默认补 `X-Client-Instance`、`X-Request-ID`；取消动作会自动携带 `X-Cancel-Reason`。
  - `cancel_requested` 事件现在可追踪 `payload.reason` 与 `headers.x_cancel_reason`。
- 2026-02-24: Gemini 质量闸门增强（默认开启）：
  - 新增 `CHATGPTREST_GEMINI_ANSWER_QUALITY_GUARD=1`：自动清理 Gemini 答案前缀 UI 回显噪声，并在元数据/事件中记录 `answer_quality_guard`。
  - 新增可选严格门禁 `CHATGPTREST_GEMINI_SEMANTIC_CONSISTENCY_GUARD=1`：检测到 `next_owner` 语义混用时降级为 `needs_followup`，防止脏稿直接终态。
  - 新增事件：`answer_quality_sanitized` / `answer_quality_detected` / `answer_semantic_risk_detected`，便于监控与告警聚合。
- 2026-02-21: Pro 测试风控守卫（默认开启）：
  - 新增阻断：`Pro + trivial prompt`（如“请回复OK”）与 `params.purpose=smoke/test` 的 Pro 请求。
  - 错误语义：`trivial_pro_prompt_blocked` / `pro_smoke_test_blocked`（HTTP 400）。
  - 客户端建议：测试优先非 Pro preset；不要再尝试通过请求参数放行 Pro smoke/trivial，请求会继续被拒绝。
- 2026-03-18: live ChatGPT smoke 围堵（默认开启）：
  - 新增阻断：`chatgpt_web.ask` 的 live smoke/test/probe 请求默认 fail-closed，不再允许低价值测试创建真实 ChatGPT 会话。
  - 覆盖范围：`purpose=smoke/test/...`、smoketest 前缀、典型 synthetic fault probes（如 `test blocked state`）、注册 smoke client 名。
  - 错误语义：`live_chatgpt_smoke_blocked`（HTTP 400）。
  - 客户端建议：smoke 默认改走 Gemini/Qwen 或 mock path；若必须例外，显式传 `allow_live_chatgpt_smoke=true` 并登记理由。
- 2026-03-19: direct live ChatGPT ask 旁路封堵（默认开启）：
  - 新增阻断：低层 `POST /v1/jobs kind=chatgpt_web.ask` 默认不再允许直打真实 ChatGPT 前端。
  - 错误语义：`direct_live_chatgpt_ask_blocked`（HTTP 403）。
  - 客户端建议：对 coding agent，真实 live ask 一律走 public MCP `advisor_agent_turn`（`http://127.0.0.1:18712/mcp`）；不要再用 `curl/chatgptrestctl` 直接创建 `chatgpt_web.ask`，也不要把 `/v3/agent/turn` 当成 coding agent 的默认接入面。
  - 受控例外：`CHATGPTREST_DIRECT_LIVE_CHATGPT_CLIENT_ALLOWLIST` 或 `params.allow_direct_live_chatgpt_ask=true`。
- 2026-03-23: coding-agent northbound 文档与接入面对齐：
  - Codex / Claude Code / Antigravity 的默认入口统一为 public advisor-agent MCP：`http://127.0.0.1:18712/mcp`。
  - repo wrapper `skills-src/chatgptrest-call/scripts/chatgptrest_call.py` 的 agent mode 默认走 public MCP，并支持：
    - `task_intake`
    - `contract_patch`
    - `workspace_request`
    - `execution_profile=thinking_heavy`
    - `--out-summary`
  - 当前 public surface 已稳定投影：
    - `task_intake`
    - `control_plane`
    - `clarify_diagnostics`
    - `lifecycle`
    - `delivery`
    - `effects`
  - 客户端建议：更新各自的 `AGENTS.md` / `CLAUDE.md` / `GEMINI.md` / wrapper skill 说明，不再教学 legacy bare MCP tools。
- 2026-02-21: MCP API auto-heal 默认开启：
  - `chatgptrest-mcp.service` 默认 `CHATGPTREST_MCP_AUTO_START_API=1`。
  - 当 MCP 访问 `127.0.0.1:18711` 出现 `Connection refused` 时，会尝试本地拉起 API 并重试一次。
- 2026-02-21: 建议客户端统一透传 `params.purpose`（`prod|smoke`）：
  - 便于服务端策略审计、问题排查与 issue 归因。
- 2026-02-21: Client Issue TTL 自动收口（guardian）：
  - 默认 `worker_auto + status=open/in_progress + 72h 无复发` 自动标记为 `mitigated`。
  - 关键参数：`CHATGPTREST_CLIENT_ISSUE_AUTOCLOSE_*`。
- 2026-03-09: Client Issue 第二阶段自动结案（guardian）：
  - 默认 `worker_auto + status=mitigated + 同客户端/同 kind 3 次 qualifying success + 无复发` 自动标记为 `closed`。
  - 关键参数：
    - `CHATGPTREST_CLIENT_ISSUE_CLOSE_AFTER_SUCCESSES`
    - `CHATGPTREST_CLIENT_ISSUE_CLOSE_MAX`
- 2026-02-22: Issue 上报防误报保护（默认开启）：
  - 非 `worker_auto` 的 `/v1/issues/report` 若引用作业已成功完成（`job_id` 或 `metadata.job_ids`），会返回 `409 IssueReportJobAlreadyCompleted`（避免把中间态误判成 open issue）。
  - 如需复盘已完成作业，显式传 `metadata.allow_resolved_job=true`（或 `force=true`）。
  - 客户端上报规范：优先传主 `job_id`；若有关联作业再放 `metadata.job_ids`（按时间顺序，最后一个视为 `latest_job_id`）。
- 2026-02-21: MCP 后台等待（非阻塞）：
  - 新增工具：`chatgptrest_job_wait_background_start|get|list|cancel`，建议客户端在长任务时使用，避免前台 `job_wait` 阻塞 agent。
- 2026-02-16: Client Issue Ledger 增强：
  - `GET /v1/issues` 新增筛选参数：`kind`、`source`、`fingerprint_hash`、`fingerprint_text`、`since_ts`、`until_ts`（见 `docs/contract_v1.md`）。
  - worker 新增自动问题登记（默认开启，`source=worker_auto`），可通过 `CHATGPTREST_ISSUE_AUTOREPORT_ENABLED` 与 `CHATGPTREST_ISSUE_AUTOREPORT_STATUSES` 调整。
- 2026-02-12: ChatGPT Web `.zip` 附件默认按原样上传；如遇 Acrobat connector stub，优先在 ChatGPT 里禁用 Adobe Acrobat App。
- 2026-02-12: Pro 质量守卫新增严格模式：按 UI 是否出现 `Thought for ...` 进行 fail-closed 判定（`CHATGPTREST_THOUGHT_GUARD_REQUIRE_THOUGHT_FOR=1`）。
- 2026-02-12: Deep Research 导出增强：优先尝试 Export→Word(DOCX) 并用 pandoc 转 GFM Markdown，改善“落盘像纯文本”的问题（`answer_format=markdown`）。
- 2026-02-12: retryable/error 结果补充 `phase` / `conversation_url` / `conversation_id` 字段，便于客户端定位与继续 follow-up。
- 2026-02-11: 新增 `kind=qwen_web.ask`（Qwen Web 自动化，独立 CDP，`preset=deep_thinking|deep_research|auto`，默认 `deep_thinking`，`deep_research` 可能触发日配额）。
  - 需要同步登记项目的用法文档与 `AGENTS.md`，补充 Qwen 使用边界（独立 Chrome、无代理、配额、跨 provider conversation_url 禁止混用）。
