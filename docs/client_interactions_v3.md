# ChatgptREST v3 — Client Interaction Matrix & Gaps (for full auto closed-loop)

目标：从 **client（REST/MCP 调用方）** 的视角，把与 ChatgptREST 的交互模式“穷举列清”，并标注当前实现下的 **可观测性/自愈闭环** 缺口（后续改造以“补齐闭环”为准绳）。

本文件只做事实枚举与缺口定位；具体 REST 契约请以 `docs/contract_v1.md` 为准。

## 0) Client 类型（按真实调用形态划分）

1. **REST client**：直接调用 `POST /v1/jobs` → `/wait` → `/answer|/conversation`。
2. **Public MCP client**：通过 `chatgptrest_agent_mcp_server.py` 暴露的 agent-level MCP tools 调用 `/v3/agent/*`（默认只暴露 `advisor_agent_turn/status/cancel`）。这是 coding agent client 的推荐接入面。
3. **Admin MCP client**：通过 `chatgptrest_admin_mcp_server.py` 暴露 legacy broad MCP tools（仅供 ops/debug 用，见 `chatgptrest/mcp/server.py`）。
3. **CLI client**：`chatgptrestctl`（`python -m chatgptrest.cli` 的封装），默认附带 `X-Client-*` 追踪头，适合 agent 可解析调用。
4. **Ops/守护进程类 client**：
   - `ops/monitor_chatgptrest.py`：只读监控（偏“观测”）。
   - `ops/maint_daemon.py`：故障采证 + 触发 `repair.*` +（v3）写入 incident/action 状态并可自动 pause（偏“闭环”）。

## 1) REST 交互（按 endpoint/行为穷举）

### 1.1 创建作业：`POST /v1/jobs`（必带 `Idempotency-Key`）

建议统一附带追踪头：
- `X-Client-Name`（调用方名称）
- `X-Client-Instance`（调用方实例）
- `X-Request-ID`（每个 HTTP 请求唯一）

**交互目的**
- 提交一次“有状态”的异步任务：ask、导出、修复、开 PR 等。

**常见输入形态（按 kind 分组）**
- `chatgpt_web.ask`：`input.question`（可跟 `conversation_url|parent_job_id` 追问），可带 `file_paths`。
- `gemini_web.ask`：`input.question`，可带 `file_paths`（Drive 上传链路），可选 `github_repo` + `params.enable_import_code=true`。
- `gemini_web.generate_image`：`input.prompt`，可带参考图 `file_paths`（同 Drive 链路）。
- `repair.check`：诊断（不发送 prompt），可带 `input.job_id|symptom|conversation_url`。
- `repair.autofix` / `repair.open_pr`：Codex 驱动的修复/出 patch（不发送 prompt）。

**成功响应**
- HTTP 200 + `JobView`（如果同 key+payload 已存在，返回同一个 `job_id`）。

**失败/冲突响应（当前实现）**
- HTTP 400：输入校验失败（如 preset 缺失/非法、`file_paths` 不存在、Gemini `github_repo` 但未开启 `enable_import_code` 等）。
- HTTP 409：
  - `detail.error="conversation_busy"`：对同一 `conversation_url` 的 follow-up 触发单会话单飞（见 `chatgptrest/core/job_store.py` + `chatgptrest/api/routes_jobs.py`）。
  - `detail` 为字符串：Idempotency-Key 与 payload 不一致（`IdempotencyCollision`，见 `chatgptrest/core/idempotency.py` + `chatgptrest/api/routes_jobs.py`）。
- HTTP 401：若设置 `CHATGPTREST_API_TOKEN`，则所有 endpoint 需要 `Authorization: Bearer ...`（见 `chatgptrest/api/app.py`）。

**client 侧必须处理的分支**
- 遇到 409 `conversation_busy`：
  - 直接 `/wait` 当前 active_job（服务端已返回 `active_job_id`），或
  - 业务允许时设置 `params.allow_queue=true`（但 send worker 仍会按 conversation_id 做串行）。
- 遇到 409 idempotency collision：说明 client 自身 key 复用策略/参数规范化不一致（尤其是 `file_paths` 的绝对/相对表示）；必须修正请求构造（否则无法安全重试）。

**闭环缺口（需要补强）**
- 缺口 A：无“系统暂停/退避”显式信号给 client（pause 在 worker claim 阶段生效，client enqueue 仍成功，但可能长期不被处理）。
- 已补齐：idempotency collision 的 409 `detail` 现在返回结构化对象（`error=idempotency_collision` + `existing_job_id/request_hash` 等字段），便于机器处理与自动定位。

### 1.2 查询状态：`GET /v1/jobs/{job_id}`（别名：`/result`）

**交互目的**
- 获取当前状态机快照（status/phase/attempts/not_before/retry_after/paths）。

**关键字段（对 client 决策最重要）**
- `status`：`queued|in_progress|cooldown|blocked|needs_followup|completed|error|canceled`
- `phase`：`send|wait`
- `retry_after_seconds`：基于 `not_before` 计算（用于 cooldown/排队退避）
- `reason_type` / `reason`：仅在 `blocked/cooldown/needs_followup/error/canceled` 时可见
- `conversation_export_path`：对话导出物（分片拉取）
- `path` + `preview`：answer 存储路径 + 预览

**闭环缺口（需要补强）**
- 缺口 C：缺少“系统级状态”维度的可观测字段（pause、最近 incident、维护动作等）；client 只能看到单 job。

### 1.3 长轮询：`GET /v1/jobs/{job_id}/wait`

**交互目的**
- 在 `timeout_seconds` 内轮询直到进入 done-ish（`completed|error|canceled|blocked|cooldown|needs_followup`）或超时。

**重要事实**
- REST `/wait` 不会“自动跨越 cooldown”（client 仍需按 `retry_after_seconds` 再次调用）。
- MCP wrapper 的 `chatgptrest_job_wait` 会在 cooldown 状态下 sleep 到 `retry_after_seconds` 再继续等（见 `chatgptrest/mcp/server.py`）。
- MCP `chatgptrest_job_wait` 现支持长等待自动后台化：当请求超时很长时，可直接返回 `wait_mode=background + watch_id`，避免前台阻塞。

**闭环缺口（需要补强）**
- 已补齐：REST `/v1/jobs/{job_id}/wait` 新增可选 `auto_wait_cooldown=1`（在 timeout_seconds 内自动跨越 cooldown 继续等，避免 REST client 侧重复实现等待策略）。

### 1.4 事件读取：`GET /v1/jobs/{job_id}/events`

**交互目的**
- 增量拉取 job event 日志（DB `job_events` 表）。

**闭环缺口（需要补强）**
- 缺口 E：无“全局事件流/按时间窗聚合查询”（monitor/daemon 要做全局观测只能自己扫 DB 或读 artifacts）。

### 1.5 拉取结果内容（分片）

1) `GET /v1/jobs/{job_id}/answer`
- 仅在 `status=completed` 且 answer artifact 存在时可读；否则 409/503。

2) `GET /v1/jobs/{job_id}/conversation`
- 仅在 `conversation_export_path` 存在时可读；否则 409/503。

**闭环缺口（需要补强）**
- 缺口 F：artifact 缺失时 503 只能返回字符串，缺少 “如何自愈/如何定位” 的结构化线索（例如：建议触发 `repair.check`、导出路径期望值、sha256/长度期望等）。

### 1.6 取消：`POST /v1/jobs/{job_id}/cancel`

**交互目的**
- 请求取消（queued 直接转 canceled；in_progress 仅标记 cancel_requested_at，等待 worker 尽快收敛）。

**闭环缺口（需要补强）**
- 缺口 G：缺少“cancel 原因/操作者/幂等取消”的更强语义（目前已有 cancel attribution event，但对 client 侧统一治理不足）。

### 1.7 健康检查：`GET /healthz`（别名：`/health`、`/v1/health`）

**当前实现**
- 恒定 `{ok:true,status:"ok"}`（未包含 DB/driver/daemon/pause/backlog 信息）。

**闭环缺口（需要补强）**
- 缺口 H：缺少“可运营级健康与背压信号”，client 无法在 enqueue 前判断服务处于何种退避/暂停状态。

## 2) MCP 交互（薄封装，但对“coding agent client”是事实标准）

对外约束：
- Codex / Claude Code / Antigravity 这类 coding agent 默认只应连接 public MCP `http://127.0.0.1:18712/mcp`。
- `/v3/agent/*` REST 保留给内部 runtime、OpenClaw/插件、运维与验证链路；不要把它当作别的 coding agent 的默认集成面。
- `chatgptrest_admin_mcp_server.py` 暴露的 broad/admin surface 仅供 ops/debug，不是正常生产接入面。

### 2.1 低层 REST 适配工具

这些工具基本一一映射 REST endpoint：
- `chatgptrest_job_create`
- `chatgptrest_job_get`
- `chatgptrest_job_wait`
- `chatgptrest_job_wait_background_start`
- `chatgptrest_job_wait_background_get`
- `chatgptrest_job_wait_background_list`
- `chatgptrest_job_wait_background_cancel`
- `chatgptrest_job_cancel`
- `chatgptrest_job_events`
- `chatgptrest_answer_get`
- `chatgptrest_conversation_get`

**闭环相关差异点（相对 REST）**
- `chatgptrest_job_wait` 具备：
  - cooldown 自动 sleep 后继续等；
  - 长等待自动后台化（可配置阈值）；
  - 前台等待硬上限（避免“单次调用傻等很久”）；
  - 可选自动提交 `repair.check`；
  - 可选自动提交 `repair.autofix`。
- `chatgptrest_job_wait_background_*` 具备：
  - 把 wait 放到 MCP 后台 task，调用立即返回（Codex 可继续处理其他任务）；
  - 可按 `watch_id/job_id` 查询、枚举、取消（含心跳字段 `heartbeat_at/poll_count/last_job_status`）；
  - 若 MCP 重启导致 watcher 丢失，可在 `..._background_get(job_id=...)` 时自动恢复；
  - 可通过 tmux 控制面板消息提示完成。

### 2.2 便捷提交工具（把 contract 固化为 tool 参数）

- `chatgptrest_chatgpt_ask_submit`
- `chatgptrest_gemini_ask_submit`
  - 支持 `deep_research: bool`，可直接触发 Gemini Deep Research 流程（与 `github_repo` 导入代码互斥）。
- `chatgptrest_gemini_generate_image_submit`
- `chatgptrest_repair_check_submit`
- `chatgptrest_repair_autofix_submit`
- `chatgptrest_repair_open_pr_submit`

**闭环缺口（需要补强）**
- 已补齐（需启用）：MCP 自动 repair 的限频/去重可通过 DB 持久化（`CHATGPTREST_MCP_PERSIST_RATE_LIMITS=1`；`ops/start_mcp.sh` 默认开启），重启 MCP 进程后窗口状态不丢失。

## 3) 闭环所需的“系统级交互”（v3 进展与剩余缺口）

下列交互不是单个 job 能解决的，但对“全自动闭环 + client 可预期行为”是必要的：

1) **Pause / Drain（系统退避）**
- 已补齐：REST `GET/POST /v1/ops/pause` + MCP `chatgptrest_ops_pause_get|set`（见 `docs/contract_v1.md`）。
- 行为补强：enqueue 时若命中 pause，会写入 `job_deferred_by_pause` 事件并把 `not_before` 推迟，便于 client 看到显式退避。

2) **Incidents（故障态聚合）与 Remediation Actions（动作审计）**
- 已补齐：REST `GET /v1/ops/incidents` / `GET /v1/ops/incidents/{incident_id}` / `GET /v1/ops/incidents/{incident_id}/actions` + 对应 MCP tools。
- 剩余缺口：暂无“按 fingerprint 查询/聚合视图/写入备注/人工 ACK”等 ops 写接口（如需要需另行扩展）。

3) **作业检索/对账**
- 已补齐：REST `GET /v1/ops/jobs`（summary list）与 `GET /v1/ops/idempotency/{idempotency_key}`（按幂等键反查 job_id）+ 对应 MCP tools。
- 剩余缺口：暂无“按 client 元数据过滤/按时间窗聚合/全文检索”等更强查询能力（需要根据 registry 里的 client 使用形态再扩展）。

4) **全局事件流**
- 已补齐：REST `GET /v1/ops/events?after_id=&limit=`（跨 job 的游标式拉取）+ 对应 MCP tool。
- 剩余缺口：暂无 SSE/WebSocket 推送；目前仍以轮询为主。

5) **可运营级 health/status**
- 已补齐：REST `GET /v1/ops/status`（pause + jobs_by_status + active_incidents + last_job_event_id）。
- 剩余缺口：`/healthz` 仍为静态 ok（未纳入 driver/Chrome/daemon 心跳与 backlog 深度诊断）；如需要可在后续引入更强 health 语义。

## 4) Public Agent Northbound Lifecycle / Delivery Surface

`/v3/agent/*` 与 public MCP 现在已经不是“只返回 answer + next_action 的薄壳”。

对 coding agent 来说，当前 northbound surface 还会稳定投影：
- `task_intake`
- `control_plane`
- `clarify_diagnostics`
- `delivery`
- `lifecycle`
- `effects`

其中建议 client 优先读：
- `lifecycle.phase`
  - `accepted`
  - `clarify_required`
  - `progress`
  - `completed`
  - `failed`
  - `cancelled`
- `delivery.mode`
  - `sync`
  - `deferred`
- `effects.workspace_action`
  - 仅在 workspace action / workspace clarify 路径出现

对 wrapper 的当前约定：
- `skills-src/chatgptrest-call/scripts/chatgptrest_call.py` 在 agent/public MCP 路径下，stdout 直接打印 raw public-agent JSON
- `--out-summary` 会额外写出一个 wrapper summary 文件，包含：
  - `mode=agent_public_mcp`
  - `session_id`
  - `route`
  - `lifecycle`
  - `delivery`
  - `effects`
  - `result`（完整 raw 响应）
### public agent 高层执行档位

- 默认 research 会走 `deep_research` 或 `report`，适合证据密集或成稿型任务。
- 如果你要的是“比 quick ask 更深，但不要 deep research 那么慢”，应显式传：
  - `execution_profile="thinking_heavy"`
  - 或兼容地传 `depth="heavy"`
- `thinking_heavy` 的定位是：
  - 快一点的 premium reasoning
  - 带一点 websearch 补足
  - 不等同于 research dossier / deep research
