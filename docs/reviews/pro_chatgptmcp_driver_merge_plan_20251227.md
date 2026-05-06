# Pro Plan: chatgptMCP Driver Merge (2025-12-27)

Source
- job_id: 92e2394b99c04f28ac11a591f39c9897
- conversation_url: https://chatgpt.com/c/694fb4eb-1754-8320-818e-ffec9aaf8b3c
- retrieval: wait-only pull via ChatgptREST executor (no new prompt)

---

下面是一个“**把 chatgptMCP 代码并入 ChatgptREST 内部 driver**”的可落地开发计划（基于你附件里 **ChatgptREST** 现状与耦合点来设计），重点目标是：**不改变对外 REST/MCP v1 契约**、不破坏现有“两段式调度（send/wait）”语义、同时把 Chrome/CDP/selector/会话导出等核心能力从外部 chatgptMCP repo 迁入并可控演进。

---

## 0. 现状基线（以你附件代码为准）

### 当前调用链

* Client → **ChatgptREST REST API** → SQLite jobdb → worker（`send|wait|all`）→ **executor** → **McpHttpClient** → chatgptMCP（HTTP MCP server）→ Chrome/CDP → chatgpt.com
* MCP 适配器：`chatgptrest_mcp_server.py` / `chatgptrest/mcp/server.py` 只是 REST 的 thin wrapper，跟 chatgptMCP 是两条独立 MCP 链路。

### 目前与 chatgptMCP 的硬耦合点（必须保留/替换）

1. **核心 driver 边界在 executor**

* 文件：`chatgptrest/executors/chatgpt_web_mcp.py`
* 依赖工具（tool_name）与关键字段：

  * `chatgpt_web_blocked_status`：`blocked / seconds_until_unblocked / blocked_until / reason`
  * `chatgpt_web_ask*`：`status / answer / conversation_url / blocked_state / error / error_type / retry_after_seconds / not_before / debug_timeline / debug_artifacts / answer_saved / answer_truncated / answer_id / answer_chars`
  * `chatgpt_web_wait`：`status / answer / conversation_url`（executor 还写入 `_wait_for`）
  * `chatgpt_web_wait_idempotency`、`chatgpt_web_idempotency_get`
  * `chatgpt_web_answer_get`（用于长答案 rehydrate）

2. **会话导出在 worker**

* 文件：`chatgptrest/worker/worker.py` 中 `_maybe_export_conversation()`
* 调用 `chatgpt_web_conversation_export`，并把 `export_path` 文件复制到 `artifacts/jobs/<job_id>/conversation.json`，再写 DB 字段（`conversation_export_*`）。

3. **运维与监控脚本依赖 chatgptMCP 的状态与工具**

* `docs/runbook.md`、`docs/maint_daemon.md`
* `ops/maint_daemon.py` 会调用：

  * `chatgpt_web_self_check / chatgpt_web_capture_ui / chatgpt_web_rate_limit_status / chatgpt_web_blocked_status`
* `ops/monitor_chatgptrest.py`/`maint_daemon` 默认读 `../chatgptMCP/.run/chatgpt_blocked_state.json`

> 结论：要“并入 driver”，必须至少解决：
> **（a）executor/worker 的 tool surface 替换**、**（b）idempotency 与 answer_id 这类跨进程稳态能力**、**（c）blocked_state/证据采集**、**（d）tab/Chrome 资源上限**。

---

## 1) 阶段 / 里程碑拆分（每阶段目标与可交付物）

下面的分期策略遵循“先把边界抽象出来 → 再搬运实现 → 再做稳定性与资源治理 → 最后灰度/回滚”，确保任何阶段都能交付可运行系统。

---

### 里程碑 M0：接口冻结与“driver 边界层”抽象（1–2 天）

**目标**

* 在 ChatgptREST 内部先把“driver 调用”从具体 MCP HTTP 客户端中剥离出来，形成可插拔的 backend。
* 冻结“内部 driver contract”：哪些 tool 名字/字段是 ChatgptREST 必须依赖的（即使未来不走 MCP，也要能等价表达）。

**关键改动点**

* 新增一个非常薄的抽象层：`ToolCaller`（或 `ChatGPTWebBackend`）接口：

  * `call_tool(tool_name, tool_args, timeout_sec) -> dict`
  * 先用现有 `McpHttpClient` 实现这个接口（不改行为）。
* executor 与 `_maybe_export_conversation` 只依赖 `ToolCaller`，而不是硬编码 `McpHttpClient(url=cfg.chatgpt_mcp_url)`。

**可交付物**

* `chatgptrest/driver/api.py`：声明 tool contract（字段约定写在 docstring 或 pydantic model）
* `chatgptrest/driver/backends/mcp_http.py`：对现有 `McpHttpClient` 的适配
* executor/worker 改造完成，但默认仍走原 chatgptMCP URL，功能不变
* pytest 全绿（至少现有单测不退化）

---

### 里程碑 M1：把 chatgptMCP 代码“搬进 repo”并能作为库运行（3–5 天）

**目标**

* 代码层面消除跨 repo 依赖：chatgptMCP 的实现代码进入 ChatgptREST（作为子包/子模块）。
* 先不急着改调用方式：可以继续以 MCP tool 的形式暴露，降低改动风险。

**实现策略（推荐两条并行兼容）**

* **策略 A：同进程嵌入 toolset（EmbeddedToolCaller）**
  在 worker 进程内直接调用 chatgptMCP 的 tool 实现函数（不经过 HTTP）。
  适合：单 worker（`role=all`）/开发环境。
* **策略 B：内置 driver daemon（同 repo，同二进制）**
  把原 chatgptMCP 的 MCP server 入口搬到 ChatgptREST 内，比如 `chatgptrest_driver_server.py`，仍提供 `chatgpt_web_*` 工具。
  适合：两段式部署（`send`/`wait` 多进程），保证跨进程共享 idempotency / tab 管理 / blocked_state。

> 我建议把 **B 作为默认生产形态**（因为你现有两段式调度的优势依赖“driver 侧状态持续存在”），A 作为开发/小规模模式。

**可交付物**

* `chatgptrest/driver/chatgpt_web/…`：迁入的 chatgptMCP 核心代码（CDP、selector、export、blocked_state、answer_store、idempotency_store 等）
* `chatgptrest_driver_server.py`：内置 driver MCP server 的启动入口（端口可继续用 18701 以便 ops 平滑切换）
* `pyproject.toml` 增补 driver 所需依赖（建议以 optional extra 方式：`chatgptrest[driver]`，避免开发/CI 过重）
* 基本 smoke：能启动 driver、能 `self_check`、能 `blocked_status`、能打开 chatgpt.com

---

### 里程碑 M2：打通 ChatgptREST ↔ 内置 driver 的全链路（5–8 天）

**目标**

* 在不改 REST/MCP v1 对外契约的前提下，把实际执行从“外部 chatgptMCP”切到“内置 driver”。
* 确保两段式调度/超时语义/答案完整性（rehydrate+export reconcile）全部对齐。

**关键任务**

1. **配置开关与运行模式**

* `CHATGPTREST_DRIVER_MODE = external_mcp | internal_mcp | embedded`

  * external_mcp：现状
  * internal_mcp：指向同 repo 的 driver server（仍走 MCP HTTP）
  * embedded：worker 内嵌调用（不建议两进程）
* 新增 `CHATGPTREST_DRIVER_URL` 或沿用 `CHATGPTREST_CHATGPT_MCP_URL` 但允许指向内置 driver。

2. **工具面（tool surface）对齐**

* 内置 driver 必须实现至少这些工具（与现有耦合一致）：

  * `chatgpt_web_blocked_status`
  * `chatgpt_web_ask` / `chatgpt_web_ask_pro_extended` / `chatgpt_web_ask_web_search` / `chatgpt_web_ask_deep_research`
  * `chatgpt_web_wait`
  * `chatgpt_web_idempotency_get` / `chatgpt_web_wait_idempotency`
  * `chatgpt_web_answer_get`
  * `chatgpt_web_conversation_export`
  * 运维用：`chatgpt_web_self_check` / `chatgpt_web_capture_ui` / `chatgpt_web_rate_limit_status` / `chatgpt_web_clear_blocked`

3. **字段契约对齐（非常关键）**

* executor 依赖字段必须保留：

  * `debug_timeline` 中的 `phase in {"sent","user_message_confirmed"}`（用于 pro fallback 的“是否已发送”判断）
  * `debug_artifacts.text`（用于 "Writing code" + "Answer now" 卡死检测）
  * `blocked_state.reason`（尤其 `unusual_activity`）
  * `answer_saved/answer_id/answer_chars/answer_truncated`（rehydrate）
  * `retry_after_seconds/not_before`（用于 worker 的 wait requeue 调度）

4. **会话导出写入路径对齐**

* 让 driver 支持把 export 直接落到 ChatgptREST 的 job 目录（最佳），或者继续返回 export_path 再由 worker copy（兼容）。
* 建议改造：`chatgpt_web_conversation_export` 支持参数 `dst_path`（可选）

  * 若提供 `dst_path=artifacts/jobs/<job_id>/conversation.json`，driver 直接写，worker 只做 meta 入库，减少跨目录复制与权限问题。

**可交付物**

* ChatgptREST 在 `internal_mcp` 模式下完整跑通：

  * `POST /v1/jobs` → send worker（phase=send）→ `in_progress` → release_for_wait → wait worker → `completed` → `/answer` 可读
* `CHATGPTREST_SAVE_CONVERSATION_EXPORT=1` 时 `/conversation` 可读且格式兼容现有 `_extract_answer_from_conversation_export`
* `format_prompt` 二次发送仍受 `CHATGPTREST_MIN_PROMPT_INTERVAL_SECONDS` 节流且不会重复发送

---

### 里程碑 M3：浏览器/标签页资源治理（TabManager + CDP/Chrome 保护）（5–7 天）

**目标**

* 避免“tab 过多 → Chrome 内存爆 → 崩溃/卡死”，并且与两段式 wait 机制兼容。

**核心设计（推荐实现为 driver 内部的 TabManager）**

* 目标：**把“并发等待”从“多 tab 常驻”改为“受控 tab 池 + 可重入恢复”**，同时不破坏 answer 的可靠性。

建议策略分层：

1. **Tab 上限与分类**

* `max_tabs_total`（硬上限，默认 8–12，根据机器内存调）
* `max_tabs_pinned`（保留 2–3 个“工作 tab”：send_tab / wait_tab / export_tab）
* 其余为“会话 tab”（必要时才持有）

2. **会话 tab 生命周期**

* 发送后若返回 `in_progress`：

  * 若系统稳定，允许保留 1 个对应 conversation_url 的 tab（便于后续 wait 低成本轮询）。
  * 但必须打上 `last_used_ts`，并配置 `idle_ttl_seconds`（如 10–20 分钟无活动则关闭）。
* 若 `max_tabs_total` 触顶：

  * 优先关闭 **idle** 的会话 tab（已完成/已导出/长时间未触达）
  * 如果全是活跃 in_progress：触发“降级等待策略”（下面第 3 点）或直接进入 `cooldown`/`needs_followup`，避免继续开 tab。

3. **等待策略：短锁轮询 + 可重开**

* wait worker 的 `chatgpt_web_wait` 不应长时间占用一个 tab 做“忙等”：

  * 采用循环：每次获取 tab → 检查状态/抓取答案片段 → 释放 tab → sleep
  * 这样 send worker 仍能在间隙拿到 send_tab 执行下一次发送（符合两段式设计初衷）
* 当目标 conversation_url 的 tab 不存在：

  * 用 wait_tab 临时导航到 conversation_url，读取最新 assistant 内容，再导航回空白页/保留
  * 这个方式在 tab 池很小的情况下依然能工作（但要评估“关闭/切换页面会不会中断生成”的实际影响；保守起见，对“正在生成”的会话尽量保留 tab）

4. **Chrome 健康保护阈值**

* 观测与防护动作（driver 内部）：

  * `cdp_connected`、`num_targets/tabs`、`reconnect_count`
  * 若连续 N 次 CDP 调用失败：进入 `cooldown` 并写明 `reason_type=CDPDisconnected`
  * 若 tab 数超过阈值：拒绝新会话、只允许 wait/export、并建议人工/maint_daemon 重启 Chrome

**可交付物**

* driver 暴露 `tab_stats`（可作为 tool 或在 `self_check` 里返回）：

  * `tabs_total / tabs_by_kind / oldest_tab_age / evictions_count`
* 对应 runbook 更新：出现 tab 触顶时如何处理（优先“关闭 idle tab/重启 Chrome”，而不是不断重试发送）

---

### 里程碑 M4：失败/风控处理闭环（blocked/cooldown/Cloudflare）+ 可观测性（3–6 天）

**目标**

* 让 driver 在遇到 Cloudflare/登录失效/异常活动等情况时：

  * **不做绕过**
  * **及时降级为 blocked/cooldown**
  * **自动收集证据（HTML/截图/关键 DOM 文本/URL）**
  * **为 ChatgptREST 的 job 状态机提供可调度的 not_before/retry_after**

**实现要点**

1. **blocked_state 持久化（跨进程共享）**

* 现状 chatgptMCP 用 `.run/chatgpt_blocked_state.json`
* 合并后建议迁移到 ChatgptREST 内：

  * `CHATGPTREST_RUN_DIR/.run/driver_blocked_state.json`（或继续兼容旧路径）
* 内容建议包含：

  * `blocked_until`、`reason`（枚举：cloudflare_challenge/login_required/unusual_activity/proxy_degraded/…）
  * `phase`（在哪一步触发：navigate/send/wait/export）
  * `url`（触发时页面 URL）
  * `first_seen_ts/last_seen_ts`、`count`

2. **blocked/cooldown 的语义映射**

* driver 返回：

  * `status = blocked`：明确需要人工介入（challenge/login）
  * `status = cooldown`：明确可自动重试（短暂风控/网络波动）
* 并附带：

  * `error_type`（如 `Cloudflare`, `LoginRequired`, `UnusualActivity`, `ProxyDegraded`）
  * `retry_after_seconds`、`not_before`（供 worker `release_for_wait` 调度）

3. **Cloudflare/验证码识别（只识别不绕过）**

* 识别信号来源（driver 内）：

  * URL 命中：`/cdn-cgi/`、challenge path
  * DOM 文本：`Checking your browser` / `verify you are human` / `Cloudflare Ray ID`
  * 标题/关键元素
* 动作：

  * 抓证据：`capture_ui` + `dump_html` + `dump_text`
  * 写 blocked_state 并返回 `blocked`

4. **与 ChatgptREST 既有“卡死检测”对齐**

* 你现有 executor 已实现：

  * debug_text 含 “Pro thinking • Writing code” + “Answer now” → `needs_followup`（并给 300s not_before）
* 合并后 driver 需要继续产出 debug_artifacts.text 或更直接的 `ui_markers`，确保 executor 仍能判定。

**观察指标（建议至少落地为 job_events + driver 日志）**

* job 维度（可写入 `job_events` 与 `artifacts/jobs/<job_id>/run_meta.json`）：

  * `driver.ask.latency_ms`, `driver.wait.poll_count`, `driver.wait.total_wait_ms`
  * `driver.selector_failures[]`（selector 名称 + step）
  * `driver.blocked.reason`, `driver.blocked.url`
  * `driver.answer.truncated`, `driver.answer.rehydrated`
  * `driver.export.ok/latency_ms`
* 全局维度（driver 自己的 JSONL 或 metrics）：

  * `tabs_total`, `tabs_evicted`, `cdp_reconnects`, `chrome_crash_suspect`
  * `blocked_state.active`、`blocked_state.reason_topk`
  * `send_rate`（实际发送频率；与 ChatgptREST 的 61s 节流对齐）

**可交付物**

* `ops/maint_daemon.py` 改造：证据采集从“外部 chatgptMCP”切为“内置 driver”
  （工具名可保持不变，减少运维切换成本）
* `ops/monitor_chatgptrest.py` 默认读取新的 blocked_state 文件路径（同时兼容旧路径一段时间）

---

### 里程碑 M5：测试体系 + 灰度发布 + 回滚（4–7 天）

**目标**

* 保证迁移不破坏对外契约，且出现问题能快速回滚到 external_mcp。

**可交付物**

* 单测/集成/回归/压测计划落地（见第 6 节）
* 发布开关（driver_mode）+ 回滚文档（见第 6 节）
* 生产灰度策略（先 canary 再全量）

---

## 2) 需要迁移的核心模块/依赖与耦合点（按“必须/建议”划分）

### 必须迁移的核心模块（chatgptMCP → ChatgptREST）

1. **CDP 连接与会话层（Browser/CDP Client）**

* 责任：

  * 连接 `CHATGPT_CDP_URL`（类似 runbook 里的 `http://127.0.0.1:9222`）
  * 管理 target/page/session
  * 执行 DOM 查询、点击、输入、截图、导出 HTML/text
* 耦合点：

  * driver 必须稳定支持长时间运行、断线重连、跨工具调用共享同一浏览器实例。

2. **Selector/DOM 适配层（ChatGPT UI selectors）**

* 责任：

  * 输入框、发送按钮、停止生成按钮、模型选择菜单、web_search/deep_research 开关、文件上传入口、对话列表/消息节点
  * 需要“多 selector fallback”（A/B DOM 结构变化时降低故障率）
* 耦合点：

  * selector 失败要能结构化输出到 `error_type=SelectorNotFound` + `selector_name`，并触发 `capture_ui`。

3. **对话发送与等待状态机（ask/wait）**

* 责任：

  * `ask`：导航→确保登录→（可选）选择模型/模式→上传文件→输入→发送→等待直到 `timeout_seconds` 或完成
  * `wait`：在 conversation_url 上轮询生成状态/抓取最新 assistant 内容（min_chars 规则）
* 耦合点：

  * 必须产出 executor 依赖的字段：`debug_timeline`、`blocked_state`、`retry_after_seconds`、`not_before` 等。

4. **Idempotency Store（强烈建议用 driver 独立持久化）**

* 责任：

  * key：`chatgptrest:{job_id}:{preset}`（executor 已固定）
  * 值：至少 `conversation_url`、（可选）`run_id`、`last_status`、`created_at`
  * 支持工具：`idempotency_get`、`wait_idempotency`
* 耦合点：

  * 这是“两段式调度 + 防重复发送”的底座：send worker 崩溃/lease reclaim 时，必须能防止第二次发送同一 prompt。

5. **Answer Store（用于 rehydrate 长答案，可选但建议保留）**

* 责任：

  * 当 tool 输出/内存策略导致 answer 可能截断时，保存 full answer blob（文件或 sqlite）并提供 `answer_get` 分段读取（char offset）
* 耦合点：

  * `chatgptrest/executors/chatgpt_web_mcp.py` 已有 rehydrate 逻辑与单测 `test_chatgpt_web_answer_rehydration.py`，保留能避免回归。

6. **Conversation Export（会话导出）**

* 责任：

  * 生成 `dom_messages` 格式 JSON：`{"export_kind":"dom_messages","messages":[{"role":"user","text":...},{"role":"assistant","text":...}] }`
* 耦合点：

  * worker 的 `_extract_answer_from_conversation_export()` 与 `Copy code` 归一化逻辑已固定（`tests/test_conversation_export_reconcile.py`），导出格式要兼容。

7. **blocked_state / self_check / capture_ui**

* 责任：

  * blocked/cooldown 的全局门禁（stop-the-world）
  * 证据抓取（png/html/txt）
  * 健康自检（selector、登录态、CDP）
* 耦合点：

  * executor 的 preflight blocked 检查依赖 `chatgpt_web_blocked_status`
  * maint_daemon 依赖 evidence tools

### 建议迁移（提升稳定性但可分期）

* **Chrome 资源探针**：tab count / memory（用于 maint_daemon 自动判定“建议重启”）
* **网络/代理相关信号**：与 ChatgptREST 现有 `mihomo_delay_snapshot` 关联（worker 已做），driver 可以补充“当次导航的关键请求失败原因”。

---

## 3) 兼容现有 REST/MCP 契约（两段式调度、phase/send/wait、timeouts）

这里的“兼容”要分三层：**对外 API 契约**、**内部 job 状态机**、**driver 调用语义**。

### 3.1 对外 REST v1 契约保持不变

* `docs/contract_v1.md` 中：

  * `POST /v1/jobs`、`/wait`、`/answer`、`/conversation`、`/events` 等完全不变
  * `phase` 字段仍是 `send|wait`
  * `timeout_seconds/send_timeout_seconds/wait_timeout_seconds/max_wait_seconds` 语义不变
* `chatgptrest/mcp/server.py`（REST→MCP 适配器）不需要改协议；只要内部 job 执行稳定即可。

### 3.2 两段式调度（send/wait）保持不变

* 现有实现关键点（你仓库已实现）：

  * send worker：`exec_phase="send"`，只负责发送（节流在 `_throttle_chatgpt_sends` + DB rate_limits）
  * wait worker：`exec_phase="wait"`，只负责等待，不再发送 prompt
  * worker 在 `status=in_progress` 时调用 `release_for_wait()` 将 `phase` 切到 `wait` 并释放 lease
* 合并 driver 后的要求：

  * **driver 层不得破坏“wait 阶段不发送新消息”**：`chatgpt_web_wait` 只能做“读取/刷新/检查”，不得触发新的 user message。

### 3.3 timeouts 的一致性（防“send 阶段卡死导致队列停摆”）

当前 executor 已区分：

* `send_timeout_seconds`：初次 ask 的工具超时
* `wait_timeout_seconds`：每轮 wait 的工具超时
* `max_wait_seconds`：executor 的总等待上限（循环+sleep）

合并 driver 要做到：

* 每个 tool 实现都必须**尊重传入的 `timeout_seconds`**（内部用 deadline/asyncio.wait_for）
* driver 返回 `status=in_progress` 时，最好附带合理的 `retry_after_seconds`（例如 30–90s），便于 worker 用 `not_before` 做调度而不是紧密轮询。

---

## 4) 标签页/浏览器资源管理策略（避免 tab 过多 / Chrome 崩）

这是合并后最容易“把稳定性做崩”的点，建议把资源治理当作 driver 的一等功能，而不是散落在 executor/worker。

### 4.1 设计原则

1. **tab 有硬上限**（没有上限就等着崩）
2. **等待不占用独占资源**：wait 轮询要短锁、可中断、可重入
3. **会话可恢复**：tab 丢了/被回收，也能靠 `conversation_url` 重新打开继续 wait/export
4. **异常时收敛**：资源紧张时宁可 `cooldown`/`needs_followup`，也不要继续开 tab

### 4.2 推荐实现：TabManager + WorkTabs

* Tab 类型：

  * `send_tab`：专门用于发送（model 切换、附件上传、输入发送）
  * `wait_tab`：专门用于轮询检查（可临时导航到 conversation_url）
  * `export_tab`：用于导出/抓证据（必要时与 wait_tab 共用）
  * `session_tabs`（可选）：仅在“生成中必须保活”时才保留
* 配置建议：

  * `DRIVER_MAX_TABS_TOTAL=10`
  * `DRIVER_SESSION_TAB_IDLE_TTL=900`（15 分钟）
  * `DRIVER_MAX_ACTIVE_GENERATIONS=6`（超过则拒绝新 send，返回 cooldown，防止拖死）

### 4.3 回收策略（LRU + 状态优先级）

* 回收优先级（从先回收到后回收）：

  1. 已完成/已导出/空白页 tab
  2. idle 超时的 session tab
  3. 最老的 session tab（但需先确保该 conversation_url 已写入 idempotency_store/返回给 ChatgptREST）
* 达到“硬上限”时：

  * `ask` 直接返回 `cooldown`，`error_type=TabLimitReached`，并附 `retry_after_seconds`（比如 300）
  * 同时抓一次 `tab_stats + capture_ui` 作为证据

### 4.4 Chrome 崩溃前兆与保护

* 前兆信号：

  * CDP 调用超时飙升
  * target list 读取失败
  * 页面响应极慢、截图失败
* 保护动作：

  * driver 进入 `cooldown` 模式：停止 ask，只允许 wait/export/self_check
  * maint_daemon 提示人工重启 Chrome（你文档里也倾向“tab 太多优先重启 Chrome”）

---

## 5) 失败/风控处理（blocked/cooldown/Cloudflare）与观察指标

### 5.1 状态分类建议（与 ChatgptREST job 状态对齐）

* `blocked`：需要人工介入（Cloudflare challenge、登录失效、验证码）
* `cooldown`：可自动重试（短暂风控、短期网络抖动、CDP 短暂失败）
* `needs_followup`：需要人工点 UI 或调整提示（你已有“Writing code + Answer now”判定）

### 5.2 driver 的风控处理策略（不绕过，只收证据+降级）

1. **Cloudflare / 验证**

* 识别到 challenge → 立即：

  * 写 `blocked_state.json`（含 reason/url/截图路径）
  * 返回 `status=blocked`（或 `cooldown`+长 not_before，但建议 blocked 更明确）

2. **unusual activity / 模型不可用**

* 若是 `pro_extended` 且未发送成功（依赖 `debug_timeline`），executor 现有逻辑会做 preset fallback（`CHATGPTREST_PRO_FALLBACK_PRESETS`）
* driver 要保证：

  * 在“未发送成功”的路径里能准确标记 `debug_timeline`（否则 executor 会误判“已发送”导致重复发送风险）

3. **网络/消息流瞬断**

* executor 已把 `"Error in message stream"` 归类为 transient，并转 in_progress→wait；driver 侧只需把原始文本作为 `answer` 或 `error` 回传即可（executor 会兜底）。

4. **CDP 断链**

* 返回 `cooldown`，`reason_type=CDPDisconnected`，`retry_after_seconds`（建议 60–180）
* 同时建议抓 `cdp_version probe`（类似你 maint_daemon 文档提到的 `json/version`）

### 5.3 建议的观察指标（最少集）

**P0（立刻要有）**

* `blocked_count_by_reason`（cloudflare/login/unusual_activity）
* `cooldown_count_by_reason`
* `needs_followup_count`（writing_code）
* `ask_success_rate / wait_success_rate / export_success_rate`
* `avg_send_latency / avg_wait_total_time`
* `tabs_total / evictions / tab_limit_hits`
* `cdp_reconnects / cdp_errors`

**P1（有余力再加）**

* selector 命中率/失败率（按 selector_name）
* 不同 preset 的成功率与耗时分布（auto/pro/thinking）
* “从 send 到 completed”的端到端时延分位数（P50/P90/P99）

落点建议：

* job 粒度：继续写 DB `job_events` + `artifacts/jobs/<job_id>/run_meta.json`（你 worker 已在写 run_meta）
* driver 全局：JSONL（类似 `artifacts/monitor/...`），供 maint_daemon 聚合成 incident pack

---

## 6) 测试计划（单测/集成/回归/压测）与回滚策略

### 6.1 单测（Unit Tests）

**目标**：不依赖真实 ChatGPT UI，就能覆盖“契约/状态机/解析”逻辑。

建议新增/补齐的单测方向：

1. **tool 返回字段契约测试**

* 给 EmbeddedToolCaller/Mock tool 返回 dict，验证 executor：

  * pro fallback 条件（依赖 `debug_timeline`）
  * transient assistant error 处理
  * needs_followup 触发条件（debug_artifacts.text）
  * answer rehydrate（你已有 `test_chatgpt_web_answer_rehydration.py`）

2. **conversation export 解析/归一化**

* 你已有 `tests/test_conversation_export_reconcile.py`，保持并加上：

  * 多轮对话匹配
  * export 缺失/格式错误容错

3. **TabManager 纯逻辑测试**

* LRU 回收、硬上限拒绝、idle_ttl 清理等全都可以纯内存测

### 6.2 集成测试（Integration Tests）

**目标**：在有登录态 Chrome 的环境里验证 driver 与 ChatGPT UI 真实交互。

建议用 pytest marker 控制：

* `pytest -m integration` 才跑
* 依赖环境变量：

  * `CHATGPT_CDP_URL`
  * `CHATGPTREST_DRIVER_MODE=embedded|internal_mcp`
* 场景集：

  1. 最小 ask→completed（短问答）
  2. ask→in_progress→wait→completed（长一点）
  3. conversation_export 可读且能从 export 提取 answer
  4. web_search/deep_research 开关（若账号支持）
  5. file upload（本地小文件）

     > 这里要格外小心风控：频率低、文件小、内容拟人化。

### 6.3 回归测试（Regression）

* 必须跑全套现有 `tests/`（你当前测试主要覆盖契约与 worker 行为）
* 加一条“契约快照测试”：

  * 同一个 dummy job，`JobView` 字段与语义不变
* 加一条“phase 行为回归”：

  * send worker 不会 wait
  * wait worker 不会 send（可以通过 driver mock 验证未调用 ask）

### 6.4 压测/稳定性测试（Load / Soak）

因为真实 ChatGPT 有节流（61s）与风控风险，压测不能靠大量真实 ask。建议把压测拆成两类：

1. **系统层压测（不触达 ChatGPT）**

* 用 dummy executor（`dummy.echo`）大并发创建 job：

  * 测 DB 锁、lease reclaim、/wait 长轮询压力
  * 测 artifacts 写入与 chunk 读取

2. **链路 soak（低频真实 ask）**

* 用你已有 `ops/smoke_test_chatgpt_auto.py`：

  * 低频（例如每 10–20 分钟一次）
  * 观察 24h：tab 数、CDP 重连、blocked 发生率

### 6.5 回滚策略（必须做到“一条 env 就能回退”）

**核心原则**：上线后出现 UI selector 大改/driver crash，不要改代码也能回到旧链路。

建议实现：

* `CHATGPTREST_DRIVER_MODE=external_mcp` 一键回滚
* 保留 `chatgptrest/executors/chatgpt_web_mcp.py` 的 MCP HTTP 路径（至少在一个版本周期内）
* runbook 增加：

  * “driver 内置模式故障 → 改 env 指向外部 chatgptMCP → 重启 worker 即可恢复”
* 数据回滚：不需要 DB schema 回滚（除非你新增表）；如果新增 driver 自己的 sqlite（建议），其失败不影响 jobdb。

---

## 7) 估计工作量、人力、优先级与风险（含建议排期）

### 7.1 工作量估算（以“你现有 ChatgptREST + 两段式 + 运维脚本”完整对齐为标准）

> 这里按“把 chatgptMCP 完整能力迁入并稳定运行（含 tab 管理/blocked/导出/rehydrate/运维工具）”估算。

| 里程碑 | 主要内容                                                     | 人日（粗估） | 优先级       |
| --- | -------------------------------------------------------- | -----: | --------- |
| M0  | driver 边界抽象、接口冻结、executor/worker 去硬编码                    |    1–2 | P0        |
| M1  | chatgptMCP 代码迁入、可作为库/daemon 运行、依赖梳理                      |    3–5 | P0        |
| M2  | tool surface & 字段契约全对齐、全链路跑通、导出对齐                        |    5–8 | P0        |
| M3  | TabManager/资源治理/CDP 健康保护                                 |    5–7 | P0        |
| M4  | blocked/cooldown/Cloudflare 证据闭环、metrics、maint_daemon 适配 |    3–6 | P1（但建议尽快） |
| M5  | 集成测试/回归/soak、灰度与回滚文档                                     |    4–7 | P0        |

**总计**：约 **21–35 人日**

* 1 名工程师：约 4–7 周
* 2 名工程师：约 2–4 周（建议 1 人主 driver，1 人主 ChatgptREST 集成/测试/运维脚本）

### 7.2 风险清单（按影响×概率排序）

**P0 风险**

1. **Selector/DOM 变更导致大面积失败**

* 缓解：selector 集中管理 + fallback + self_check + capture_ui + 快速回滚到 external_mcp

2. **idempotency 不可靠导致重复发送**（最致命：会在同一对话里刷重复用户消息）

* 缓解：driver 侧持久化 idempotency（独立 sqlite）+ executor 继续用 `chatgptrest:{job_id}:{preset}` + send/wait 严格隔离

3. **tab 泄漏导致 Chrome 崩**

* 缓解：硬上限 + LRU 回收 + idle_ttl + 资源紧张时拒绝新 ask（cooldown）

**P1 风险**
4) **关闭/复用 tab 的策略影响“生成中的消息”**

* 缓解：对“生成中”的会话尽量保留 tab；wait 轮询短锁；必要时降级到“保守模式”（少复用、多保活，但受上限保护）

5. **deep_research/web_search/agent_mode/file upload 的 UI 路径不稳定**

* 缓解：分级支持（P1），不影响基础 ask/wait；失败时明确 `error_type=FeatureNotSupported` 并可回滚

**P2 风险**
6. **driver 与 ChatgptREST 共享 sqlite/锁竞争**（若走同 DB）

* 缓解：driver 独立存储；与 jobdb 解耦

---

## 最终建议：一条“最稳妥”的落地路线

如果你要兼顾“尽快并入 + 不丢两段式优势 + 可回滚”，我建议：

1. **先做 M0（抽象边界）**：让 executor/worker 不再“只能 MCP HTTP”。
2. **做 M1+M2：把 driver 以“内置 daemon（internal_mcp）”形态上线**：

   * worker 仍走 MCP tool 调用（最小改动）
   * 但 driver 代码/运维都在 ChatgptREST repo 内
3. **做 M3：tab 上限与回收必须在上线前就有**（否则很快出事故）。
4. **做 M4：blocked/Cloudflare 的证据闭环与熔断**（不绕过，快速止损）。
5. **最后才考虑 embedded 模式作为可选**（适合单 worker，不适合多进程两段式）。

---

如果你希望我把上面计划进一步“工程化成任务清单（按 PR/文件路径拆分）”，我也可以直接按你仓库现有结构给出：

* 每个 PR 的改动范围（具体到 `chatgptrest/executors/...`, `chatgptrest/worker/...`, `ops/...`, `docs/...`）
* 每个 PR 的验收标准（pytest + smoke + 行为断言）
* 以及 driver 工具返回字段的“最小必需字段表”（确保不踩 executor/worker 的隐式依赖）。
