# Pro Review: Coverage + Ops Gaps (ChatgptREST)

- date_utc: 2025-12-28
- chatgptrest_job_id: e61af44a385648d1b295c34c9d43e1d6
- conversation_url: https://chatgpt.com/c/69508bda-e31c-8320-a010-68b85ad987f9
- code_pack: state/chatgpt-pro-packs/chatgptrest_code_review_pack_20251228_014407Z.zip
- code_pack_commit: e4e776f4bcb8ee9f1a0c149bac924f671d66f369

---

A) 我确实打开并阅读过的 10 个关键文件路径（来自 zip）

1. `docs/handoff_chatgptrest_history.md`
2. `chatgptrest/core/config.py`
3. `chatgptrest/core/job_store.py`
4. `chatgptrest/core/artifacts.py`
5. `chatgptrest/core/idempotency.py`
6. `chatgptrest/core/mihomo_delay.py`
7. `chatgptrest/worker/worker.py`
8. `chatgptrest/executors/chatgpt_web_mcp.py`
9. `chatgpt_web_mcp/server.py`
10. `ops/maint_daemon.py`

---

B) 按维度逐条判断：已覆盖 / 部分覆盖 / 未覆盖（含对应文件/函数名与理由）

## 1) 防风控：UI 拟人化、61s send pacing、避免重复发问（同 idempotency 不重发；message stream error 不重发）

**结论：已覆盖（但仍有少量边界风险点，见 C 的 P0/P1）**

### 1.1 UI 拟人化（human-like）

* **对应实现**

  * `chatgpt_web_mcp/server.py`

    * `_human_pause()`：用于在关键 UI 动作之间插入随机停顿。
    * `_delay_range_ms() / _type_delay_ms()`：用于键入速度、动作抖动等（更像真人而非“瞬时填充/点击”）。
    * 输入/发送路径中可见多个“human pause + typing delay”的组合（你仓库里这块写得比较完整）。
* **理由**

  * 这类“拟人化”属于典型的降低 UI 自动化被识别概率的策略：非固定间隔、非固定键入速度、少量 jitter。
  * 同时仓库的 `ops/smoke_test_chatgpt_auto.py`（我额外浏览过，未列入 A 的 10 个）也强调避免明显“测试句式”的 prompt，属于运营侧的风控友好实践。

### 1.2 61s send pacing（发送节奏控制）

* **对应实现（双层节流，互补）**

  1. **ChatgptREST 侧（DB 协调，全 worker 一致）**

     * `chatgptrest/core/config.py`

       * `min_prompt_interval_seconds` 默认 **61**（`CHATGPTREST_MIN_PROMPT_INTERVAL_SECONDS`）。
     * `chatgptrest/worker/worker.py`

       * `_throttle_chatgpt_sends()`：通过 `chatgptrest/core/rate_limit.py::try_reserve()` 在 SQLite 事务里做**跨进程/跨 worker 协调**的最小间隔。
       * 记录 `send_throttled` 事件到 DB 与 artifacts 事件流，便于排障/审计。
  2. **driver（chatgpt_web_mcp）侧（UI send 动作串行 + 可选跨进程文件协调）**

     * `chatgpt_web_mcp/server.py`

       * `_min_prompt_interval_seconds()`：默认 **61**（`CHATGPT_MIN_PROMPT_INTERVAL_SECONDS`）。
       * `_chatgpt_send_prompt()`：对“真正点击发送/Enter”的动作加锁串行，并调用 `_respect_prompt_interval()`。
       * 可选的 `CHATGPT_GLOBAL_RATE_LIMIT_FILE`：允许跨进程共享“最后发送时间”，避免 driver 重启导致节奏状态丢失。
* **理由**

  * 61s send pacing 这条在你的仓库里是“强约束”：**即便 worker 并发或 driver 并发，也会被序列化/节流**，属于对风控非常关键的一层防线。
  * 另外：双层节流的副作用是“配置不一致会导致估算/行为不一致”（见 C 的 P1）。

### 1.3 避免重复发问：同 idempotency 不重发

* **对应实现（分两段：REST 作业层 + UI side-effect 层）**

  1. **REST 作业层：防重复创建作业**

     * `chatgptrest/core/idempotency.py`

       * `check_or_insert_idempotency_record()`：用 `Idempotency-Key` + 请求 hash 做幂等；同 key 不同 payload 会抛 `IdempotencyCollision`。
     * `chatgptrest/core/job_store.py`

       * `create_job()`：在 `BEGIN IMMEDIATE` 事务里做幂等判定并创建 job，避免并发重复入队。
  2. **UI side-effect 层：防重发 prompt（最关键）**

     * `chatgptrest/executors/chatgpt_web_mcp.py`

       * 对 driver 的 idempotency_key 采用稳定格式：`primary_key = f"chatgptrest:{job_id}:{preset}"`
       * 在 `phase=wait/full` 使用 `chatgpt_web_wait_idempotency` 等待同一 idempotency 关联的会话结果，不会“再发一次”。
     * `chatgpt_web_mcp/server.py`

       * 内部 idempotency DB：`MCP_IDEMPOTENCY_DB`（默认 `.run/mcp_idempotency.sqlite3`）
       * `_idempotency_begin()` / `_idempotency_commit()`：保证同一 `(namespace, tool, idempotency_key)` 的 send-type 工具不会重复产生副作用。
* **理由**

  * 这是你“重复发送”历史问题的核心修复路径：**即便 worker 由于 lease reclaim 或异常重试再次执行 send-phase，也会被 driver 的 idempotency 层拦住**。
  * 再配合两段式调度（send/wait）可把“重试”更多地导向 wait-phase，而不是 send-phase。

### 1.4 message stream error 不重发（把短暂 UI 错误当作可重试等待，而不是“完成答案”）

* **对应实现**

  * `chatgptrest/executors/chatgpt_web_mcp.py`

    * `_looks_like_transient_assistant_error()` / 相关逻辑：检测 “Error in message stream / Something went wrong …”
    * 发现后强制把结果改为 `in_progress`，并在 `phase=full` 情况下进入 `_wait_loop()`；若超过等待窗口仍未恢复，则转 `cooldown` 且 `reason_type=TransientAssistantError`。
* **理由**

  * 这直接覆盖了 `docs/handoff_chatgptrest_history.md` 里的历史点 #4（Transient assistant errors treated as retryable）。
  * 关键点在于：**等待在同 conversation 内继续，而不是重新 ask**，显著降低重复发问风险。

---

## 2) 代理/Cloudflare：mihomo 延迟探针、blocked/cooldown 证据、排障步骤是否可复盘

**结论：已覆盖（证据链条较完整；仍可在“证据包聚合”和“关联字段落库”上加强，见 C 的 P1）**

### 2.1 mihomo 延迟探针（proxy health）

* **对应实现**

  * `chatgptrest/core/mihomo_delay.py`

    * `snapshot_once()`：调用 mihomo API 拉取 proxy group、selected node 与延迟探测结果。
    * `daily_log_path()` / `append_jsonl()`：把探针记录按天落盘为 jsonl。
    * `summarize_recent()`：对某个 group:selected 聚合近期成功率/延迟等统计。
  * `chatgptrest/worker/worker.py`

    * `_record_mihomo_delay_snapshot()`：在 job 进入 `blocked/cooldown/needs_followup` 等异常状态时，抓取快照并写入：

      * `artifacts/jobs/<job_id>/mihomo_delay_snapshot.json`
      * DB job_events（type=`mihomo_delay_snapshot`）
      * 同时把 records 追加到 `artifacts/monitor/mihomo_delay/mihomo_delay_YYYYMMDD.jsonl`
* **理由**

  * 这覆盖了 `handoff_history` #8（Proxy correlation snapshots）。
  * 优点是：不仅拿“当前状态”，还会顺手算 “history summary”，能回答“是偶发还是持续劣化”。

### 2.2 Cloudflare / blocked / cooldown 的证据与冷却

* **对应实现**

  * `chatgpt_web_mcp/server.py`

    * `_raise_if_chatgpt_blocked()`：检测 Cloudflare、人机验证、登录缺失、unusual activity 等。
    * `_capture_debug_artifacts()`：在 blocked 触发时采集证据（截图/HTML/正文文本），并将路径写入 blocked_state。
    * blocked_state 落盘：`_chatgpt_blocked_state_file()`（默认 `.run/chatgpt_blocked_state.json`，可配置 `CHATGPT_BLOCKED_STATE_FILE`）
  * `chatgptrest/worker/worker.py`

    * send 之前可做 `chatgpt_web_blocked_status` preflight（你这里做得比较谨慎：blocked 直接转 retryable，不进入发送）。
    * 对 `blocked/cooldown` 结果会触发 `_record_mihomo_delay_snapshot()`，把“proxy 健康”和“Cloudflare/blocked”串起来。
* **理由**

  * 证据链齐全：**blocked 的根因 + 冷却时间 + UI证据（截图/HTML/text）+ proxy 延迟快照**。
  * 这对“可复盘排障”非常关键：你不仅能看到“被挡了”，还能看到“挡之前/挡当下代理状况”。

### 2.3 排障步骤可复盘（runbook + incident pack）

* **对应实现**

  * `ops/maint_daemon.py`

    * 周期扫描 jobs：对 `blocked/cooldown/needs_followup/error` 或 `in_progress` 超时的 job 生成 incident。
    * incident pack 结构（关键点）：

      * `artifacts/monitor/maint_daemon/incidents/<incident_id>/manifest.json`
      * `snapshots/`：包含 blocked_state、mihomo_delay_last、cdp_version 等
      * `jobs/<job_id>/`：复制 `request.json/events.jsonl/result.json/run_meta.json/.../conversation.json` 等关键证据
    * 可选：`--enable-chatgptmcp_evidence`、`--enable-chatgptmcp_capture_ui`
      会额外拉取 `blocked_status/rate_limit_status/self_check/tab_stats` 与 UI 快照（强调：不发送 prompt）。
* **理由**

  * 你现在的“复盘能力”是系统性的：**一旦异常发生，工单/证据包能把 job 级证据与 driver/proxy 级证据串起来**。
  * 这基本覆盖了你提到的“blocked/cooldown 证据、排障步骤可复盘”。

---

## 3) 长答可靠性：answer 落盘、UTF-8 byte chunk、conversation export 对账/修复、answer_id rehydrate

**结论：已覆盖（属于你仓库目前最“工程化”的部分之一；剩余风险主要是少数边界输入与运维流程自动化）**

### 3.1 answer 落盘（单一真相源 + 原子写）

* **对应实现**

  * `chatgptrest/core/artifacts.py`

    * `write_answer()`：用 staging 临时文件 + `os.replace()` 原子替换；避免写一半被读到。
    * `write_answer_raw()`：在需要时保留“原始（可能截断）输出”，便于对账。
    * `reconcile_job_artifacts()`：当 DB 记录与 artifacts 不一致时做“自愈式修复”（例如 answer 文件缺失但 metadata/备份存在）。
  * `chatgptrest/core/job_store.py`

    * `store_answer_result()`：带 lease_token 的 CAS 语义写 DB，防止“旧 worker 覆盖新结果”。
* **理由**

  * 覆盖 `handoff_history` #1（answer_path 单一真相源）和 #2（lease token + staged writes）。
  * “落盘可靠性”的核心风险（并发覆盖、部分写、路径混乱）你基本都挡住了。

### 3.2 UTF-8 byte chunk（避免 chunk 切在多字节中间导致解码破坏/截断）

* **对应实现**

  * `chatgptrest/core/artifacts.py`

    * `read_utf8_chunk_by_bytes()`：按 byte offset 读 chunk，并通过 UTF-8 continuation byte 规则校正边界，避免切坏字符。
  * `chatgptrest/api/routes_jobs.py`（我额外阅读过）

    * `/v1/jobs/{job_id}/answer` 与 `/conversation` 使用上述函数做分片读取。
* **理由**

  * 覆盖 `handoff_history` #7（UTF-8 chunking by byte offset）。
  * 这类实现是长答可靠性里最容易“隐藏出 bug”的地方，你用 byte-offset + 边界校正是正确方向。

### 3.3 conversation export 对账/修复（DOM export 规范化 + 从 export 反推完整答案）

* **对应实现**

  * `chatgptrest/worker/worker.py`

    * `_maybe_export_conversation()`：调用 `chatgpt_web_conversation_export` 并将 conversation.json 归档到 job artifacts，同时更新 DB `conversation_export_*` 字段。
    * `_normalize_dom_export_text()`：处理 `json\nCopy code\n{...}` 这类 DOM export UI 杂质，转换成 fenced code block。
    * `_extract_answer_from_conversation_export()` + `_should_prefer_conversation_answer()`：用“匹配 user question → 取其后 assistant 回复”的方式，从 export 里找更完整的答案，并在更可信时替换当前答案。
* **理由**

  * 覆盖 `handoff_history` #6（export normalization）与 #11（export fallback finalize）。
  * 你的“更可信判定”（candidate 更长且包含 current 等）能显著降低“抽错 message”导致的错误替换风险。

### 3.4 answer_id rehydrate（从 driver 持久化的大答案 blob 拉回完整文本）

* **对应实现**

  * `chatgptrest/executors/chatgpt_web_mcp.py`

    * `_rehydrate_answer_from_answer_id()`：当 `answer_truncated` 且 `answer_saved+answer_id` 存在时，调用 `chatgpt_web_answer_get` 分片拉取完整答案并替换内存答案。
* **理由**

  * 覆盖 `handoff_history` #5（Answer rehydration via answer_id）。
  * 这对“客户端/工具输出被截断”非常关键：你的系统不依赖一次 tool output 能带回全部内容。

---

## 4) 资源与稳定性：tab 上限、CDP 自动重启、send/wait 两段式、wait slice、防 send stuck（尤其附件上传卡住）

**结论：已覆盖（但 Chrome 长期运行与“证据→自愈闭环”仍可加强，见 C 的 P1/P2）**

### 4.1 tab 上限（防 Chrome 资源泄漏/爆炸）

* **对应实现**

  * `chatgpt_web_mcp/server.py`

    * 并发 page slot 信号量（tab limit）：当超过上限，返回 `cooldown` 并附带 `retry_after_seconds`（避免无限开 tab）。
    * `chatgpt_web_tab_stats` 工具（供观测/排障）。
  * `ops/maint_daemon.py`

    * incident 时可抓 `tab_stats.json`（`--enable-chatgptmcp_evidence`）。
* **理由**

  * 覆盖 `handoff_history` #15（Driver tab limit + stats）。
  * 这是“Chrome 资源泄漏”类问题最有效的第一道闸门：你无法完全阻止 Chrome 自身泄漏，但可以阻止“并发 tab 无上限”导致快速崩溃。

### 4.2 CDP 自动重启（Chrome/远程调试通道不稳定时的自愈）

* **对应实现**

  * `chatgpt_web_mcp/server.py`

    * `_ensure_local_cdp_chrome_running()`：CDP 连接前检查本地 Chrome。
    * `_restart_local_cdp_chrome()`：CDP connect 失败时可触发重启并重试（受配置开关控制）。
  * `ops/maint_daemon.py`

    * `--enable-chrome-autostart`：当 CDP down（`/json/version` 无效）时调用 `ops/chrome_start.sh`（强调“安全：已在运行则 no-op”）。
* **理由**

  * 覆盖“Chrome 不可用导致全链路停摆”的典型故障面；属于稳定性核心能力。

### 4.3 send/wait 两段式（队列堵塞治理 + 防重发）

* **对应实现**

  * `chatgptrest/core/job_store.py`

    * `release_for_wait()`：把 job phase 置为 `wait`，清 lease，并写 `wait_requeued` 事件。
    * `claim_next_job(..., phase=...)`：支持按 phase 拉取；并且 **wait phase 不消耗 attempts**（关键细节，防止 attempts 被 wait 消耗殆尽导致死锁）。
  * `chatgptrest/worker/worker.py`

    * worker role：`send|wait|all`（根据环境变量/启动脚本）；并根据 job.phase 决定执行 `phase="send"/"wait"`。
    * `wait_slice_seconds`：在 wait worker 上对 `max_wait_seconds` 做切片，避免单 job 长时间占用 worker。
* **理由**

  * 覆盖 `handoff_history` #9（Two-phase scheduling）与 #10（Timeout split）与 #11（wait refresh/export fallback）。
  * 这直接解决你提到的“队列堵塞”以及“重试时重发”的核心矛盾：**send side-effect 与 wait polling 解耦**。

### 4.4 防 send stuck（尤其附件上传卡住）

* **对应实现**

  * `chatgptrest/executors/chatgpt_web_mcp.py`

    * send 阶段若 `status=in_progress` 但缺 `conversation_url`，会：

      * 尝试 `_resolve_conversation_url_from_idempotency(primary_key)` 自救；
      * 失败则直接返回 `needs_followup`，`reason_type=SendStuckNoConversationUrl`，并给出 `retry_after_seconds`（释放 send worker，避免队列卡死）。
* **理由**

  * 覆盖 `handoff_history` #13（Attachment send stuck guard）。
  * 这是非常关键的“fail-fast”策略：宁可需要人工介入，也不要让 send worker 被一个“无 conversation_url 的 in_progress”永久吊死。

---

C) P0/P1/P2 TODO 列表（每条写清“为什么”+“怎么改”）

下面是我结合你提到的历史风险点 + 当前实现细节，给出的**最可能“还会咬人”的点**与改进路径。为了便于落地，我尽量写到具体文件/函数/落库字段级别。

## P0（高优先级：不做可能直接导致重复发送、风控升级或大面积卡队列）

### P0-1：Pro fallback 的“零重复发问”更强保证（降低误判导致二次发送的概率）

* **为什么**

  * `chatgptrest/executors/chatgpt_web_mcp.py` 里 pro preset fallback 的触发条件依赖 `sent = _is_sent(debug_timeline)`。
    `debug_timeline` 在某些异常链路里可能缺失或不完整，存在“实际上已发送，但 sent 判定为 false”的边界风险。
  * 一旦进入 fallback，使用的是不同的 idempotency_key（`chatgptrest:{job_id}:{fb}`），理论上可能产生“同一 job_id 的第二条用户消息”（最怕的事情）。
* **怎么改**

  1. 在 fallback 之前，增加一次“硬核判定”：调用 driver 的 `chatgpt_web_idempotency_get(primary_key)`（或你 executor 里已有的 `_resolve_conversation_url_from_idempotency(primary_key)`扩展返回更多字段）：

     * 如果记录显示 `sent=true` 或已有 `conversation_url`，则**强制 fallback_suppressed**，把状态改为 `in_progress` → 走 wait，不再二次 ask。
  2. 将 suppression 的判定结果落在 meta：`_fallback_suppressed_reason = idempotency_sent_true / idempotency_has_conversation_url`，便于复盘。
     3)（可选更激进但更安全）fallback 仍复用同一个 idempotency_key（primary_key），但在 tool args 里切 preset；这要求 driver 端把 “preset 变化”从 request_hash 中隔离，否则会触发 idempotency collision。若你不想改 driver，至少做第 1) 的 hard check。

### P0-2：把 driver 的关键状态文件“强制落到持久盘”，避免重启后幂等失效/blocked 状态丢失

* **为什么**

  * driver 的幂等 DB 默认在 `.run/mcp_idempotency.sqlite3`，blocked_state 默认 `.run/chatgpt_blocked_state.json`。
    如果部署环境 `.run` 是容器临时层、tmpfs 或被清理，driver 重启后：

    * 幂等缓存丢失 → worker reclaim/重试时更容易出现 UI side-effect 重放（重复发送的根源之一）。
    * blocked_state 丢失 → 可能在仍被 Cloudflare 挡住时继续尝试，导致风控恶化。
* **怎么改**

  1. 在部署规范里强制配置（并在启动时校验）：

     * `MCP_IDEMPOTENCY_DB=/persistent/state/mcp_idempotency.sqlite3`
     * `CHATGPT_BLOCKED_STATE_FILE=/persistent/state/chatgpt_blocked_state.json`
     * （如使用）`CHATGPT_GLOBAL_RATE_LIMIT_FILE=/persistent/state/chatgpt_rate_limit.json`
  2. 在 `ops/maint_daemon.py` 增加一个“配置健检”快照（不需要发 prompt）：

     * 检查上述路径是否位于可写持久盘、是否在容器重启后仍存在（可以记录 inode/挂载点信息）。
     * 如果不满足，生成一个 `category=config` 的 incident（P0 级别）。
  3. 在 `docs/runbook.md` 增加明确章节（“持久化目录要求”）。

### P0-3：为 conversation export 增加“按 job 的冷却/节流”，避免 wait slice + export fallback 造成 UI/网络压力堆叠

* **为什么**

  * 当前 `chatgptrest/worker/worker.py::_maybe_export_conversation()` **每次被调用都会尝试 export**，并不会检查：

    * 当前 job 是否刚 export 过；
    * export 是否失败过且短时间内重复失败；
    * 是否处于 blocked/cooldown 环境（此时频繁 export 可能更刺激 Cloudflare）。
  * 在 wait slice 模式下，in_progress job 可能每个 slice 都触发 export，从而形成“无 prompt 的高频 UI fetch”，仍有风控/资源风险。
* **怎么改**

  1. 在 DB 或 artifacts 里记录每个 job 最近一次 export 的时间戳与结果：

     * 方案 A：DB 新字段 `conversation_export_updated_at`（或复用 `updated_at` + event 判定）。
     * 方案 B：在 `run_meta.json` 或新增 `conversation_export_meta.json` 存 `last_attempt_ts/last_ok_ts/fail_count`（注意原子写）。
  2. 在 `_maybe_export_conversation()` 入口加规则：

     * 若距离上次成功 export < 120s：跳过（写 event：`conversation_export_skipped`）。
     * 若连续失败 >=3 且距离上次失败 < 300s：跳过（指数退避）。
     * 若 driver blocked_state 显示 blocked：跳过（除非你明确要“抓证据”，那也要全局限频）。
  3. 增加一个全局 export 限频（类似 `_throttle_chatgpt_sends` 的方式，但 key 用 `chatgpt_export`），防止多 job 同时 export。

---

## P1（中高优先级：不做会让排障/运维成本变高，或在压力/长期运行下更容易出故障）

### P1-1：统一/显式化两套 pacing 配置，避免“worker 认为 61s，但 driver 实际 90s（或反之）”导致估算与行为漂移

* **为什么**

  * ChatgptREST 用 `CHATGPTREST_MIN_PROMPT_INTERVAL_SECONDS`，driver 用 `CHATGPT_MIN_PROMPT_INTERVAL_SECONDS`。
    两者若不一致：

    * `/v1/jobs` 的排队时间估算（基于 REST 的 rate_limits 表）会偏离真实发送节奏；
    * 运维排障时会出现“看起来没违规，但 driver 仍在等”的错觉。
* **怎么改**

  * 方案 A（最简单）：runbook 强制两者一致，并在 `ops/start_driver.sh`、`ops/start_worker.sh` 里做一致性校验。
  * 方案 B（更工程化）：ChatgptREST 启动时读取 driver `chatgpt_web_rate_limit_status` 并把 min_interval 作为“真值”写入自身 config/DB（或至少写一条告警事件当不一致）。
  * 方案 C：只保留一层节流（推荐保留 worker DB 协调 + driver send_lock，但统一 min_interval 来源）。

### P1-2：incident 证据包补齐“driver debug artifacts / call log”的自动聚合（现在是“有路径但不一定被打包”）

* **为什么**

  * `chatgpt_web_mcp/server.py::_capture_debug_artifacts()` 在 Cloudflare/verify/login 等场景会生成 screenshot/html/text 文件，并把路径塞进 blocked_state。
  * 但 `ops/maint_daemon.py` 目前主要复制 blocked_state 文件本身，并不会解析其中的 artifacts 路径把对应文件也复制进 incident pack。
  * 结果：**最关键的 UI 证据可能散落在 driver 的 debug_dir，工单包里未必自包含**。
* **怎么改**

  1. 在 `ops/maint_daemon.py` 读取 `chatgptmcp_blocked_state.json`（snapshots 里已复制），解析 `artifacts` 字段：

     * 把其中存在的 screenshot/html/text 复制到 `incidents/<id>/snapshots/driver_debug/`。
  2. 若启用了 `MCP_CALL_LOG`（driver call log），也把最近 N 行 tail 到 incident pack（避免泄露敏感，默认不含 prompts/answers）。
  3. 在 manifest 里加一个 `evidence_completeness` 字段，表示是否成功收齐 driver 证据。

### P1-3：DB（job_events）与 artifacts 的生命周期治理（长期运行必做，否则性能/磁盘慢性恶化）

* **为什么**

  * `job_events` 是追加型，长期运行会膨胀；SQLite WAL/索引也会逐渐拖慢写入与查询。
  * artifacts 你已经有 `ops/cleanup_artifacts.py`，但 DB 还缺少对应清理/归档策略。
* **怎么改**

  1. 新增 `ops/cleanup_db.py`：

     * 删除 N 天前 terminal jobs 的 `job_events`（可保留汇总字段到 jobs 表或导出成压缩 jsonl）。
     * `VACUUM` 或 `PRAGMA wal_checkpoint(TRUNCATE)`（在低峰执行）。
  2. 在 `ops/systemd` 添加 timer，定期跑 cleanup。
  3. `ops/maint_daemon.py` 定期记录 DB 文件大小、WAL 大小，并在阈值触发 incident（P1）。

### P1-4：对“stuck in_progress”的自愈动作分级（现在更多是采证，下一步是“安全修复”）

* **为什么**

  * 你已经在 `ops/maint_daemon.py` 能识别 `in_progress` 超过 `expected_max_seconds` 的 stuck。
  * 但后续动作目前主要是打包证据；对于某些可自动修复的 stuck（例如 driver 断连、CDP down、tab limit 长期 hit），可以更自动化。
* **怎么改**

  * 建议把 stuck 分为三类：

    1. **环境类**（CDP down / driver不可用）：可以自动 `chrome_autostart`（你已有），并增加 driver 重启（如果是 internal_mcp 模式可控）。
    2. **资源类**（tab limit 持续 hit / Chrome 内存过高）：触发“温和重启”策略（见 P2-2 里更细）。
    3. **业务类**（对话本身卡住）：只采证，不自动继续发送；最多尝试 `conversation_export` 或 `wait_idempotency` 一次做“无副作用修复”。
  * 把自愈动作也落盘为 `actions.jsonl`（你已有 `_record_action`），并在 incident summary 里汇总。

### P1-5：proxy/Cloudflare 关联的“结构化落库字段”再补一层（方便报表与告警）

* **为什么**

  * 目前 proxy 关联主要靠 `mihomo_delay_snapshot` 事件与 daily jsonl；Cloudflare 关联主要靠 blocked_state 的 reason/phase/url。
  * 但若要做报表/告警（例如“unusual_activity 发生时，选中的节点分布/延迟/失败率”），用事件日志离线分析成本偏高。
* **怎么改**

  * 在 `jobs` 表或新增 `job_proxy_facts` 表（轻量）落：

    * `proxy_group`, `proxy_selected`, `proxy_delay_ms`, `proxy_ok_rate_recent`
    * `blocked_reason`, `blocked_phase`, `blocked_until`
  * 写入点：

    * `worker._record_mihomo_delay_snapshot()` 产生快照后，把“selected + stats”同步更新到 job 行。
    * preflight blocked_status 时把 blocked_reason/blocked_until 同步更新（不只是 last_error 文本）。

---

## P2（可优化项：提升可维护性/可观测性/边界可靠性，但短期不一定致命）

### P2-1：`/answer` 与 `/conversation` 的参数命名对齐（max_chars 实际上是 max_bytes）

* **为什么**

  * `chatgptrest/api/routes_jobs.py` 里 `answer_chunk_route(... max_chars=8000)` 实际传给 `read_utf8_chunk_by_bytes(... max_bytes=int(max_chars))`。
  * 对客户端来说会有误导：以为是“字符数”，实际更像“字节预算”。
* **怎么改**

  * API 版本不变的情况下：

    * 文档明确：`max_chars` 实为 `max_bytes`（兼容）。
  * 或引入新参数 `max_bytes`，保留旧参数但标记 deprecated，并在响应里返回 `returned_bytes`。

### P2-2：Chrome 资源泄漏的“长期运行策略”：基于指标的滚动重启（带安全门槛）

* **为什么**

  * tab limit 能限制爆炸，但 Chrome 自身长期运行仍可能内存膨胀、性能下降（典型慢性问题）。
* **怎么改**

  * 在 `ops/maint_daemon.py` 加一个“健康阈值策略”：

    * 收集：tab_stats、`/json/list` 数量、Chrome 进程 RSS（`ps`）。
    * 触发：连续 N 次超过阈值 + 当前无 send-phase job 正在执行（或 send worker idle）→ 执行温和重启。
  * 落盘：incident actions + “重启前后对比”快照，便于复盘。

### P2-3：对话 export 对账的“定位更精确”：引入 message_id/turn_id（减少误匹配）

* **为什么**

  * `_extract_answer_from_conversation_export()` 用“问题文本匹配”来定位 user message，可能在重复/相似问题场景下误选。
* **怎么改**

  * driver 在 send 时若能返回更稳定的 `user_message_id` 或 `turn_id`（基于 DOM 或 backend-api），就把它存到 job meta；
  * export 时按 id 精准取对应 assistant reply；
  * 没有 id 时退回文本匹配（兼容）。

### P2-4：把 `run_meta.json` 的写入也改成原子写（减少“半写文件”导致工具链误判）

* **为什么**

  * 当前 `_write_json()` 直接 `write_text`，进程崩溃时可能留下半文件；虽不影响主链路，但会影响 repair/排障工具。
* **怎么改**

  * 复用 `chatgptrest/core/artifacts.py` 的 staging+replace 逻辑，或新增 `artifacts.atomic_write_json()`。

---

D) 如需新增运维脚本/daemon（repair daemon）：最小可行设计（触发条件、落盘路径、降噪、避免风控风险）

我建议**新增一个“Repair Daemon（无 prompt side-effect）”**，目标是把“长答截断/对账修复/证据自包含”从人工脚本提升为常驻自愈能力，同时严格避免制造风控风险。

下面给的是“最小可行（MVP）”设计，能直接落到你现有结构里（复用 DB、artifacts、driver 工具）。

---

## D-1：Daemon 名称与运行方式

* 文件：`ops/repair_daemon.py`（新建）
* 运行模式：

  * systemd service（类似你已有的 `chatgptrest-maint-daemon.service`）
  * 单进程、单并发（默认 1），每轮扫描间隔例如 30~60s

---

## D-2：触发条件（只做“无副作用修复”，不发送任何 prompt）

Repair daemon 的触发条件建议聚焦在**“可确定修复”**的场景，避免误操作：

### 触发条件 1：Completed 但疑似截断/不完整（优先级最高）

满足以下任意组合即触发修复尝试：

* `jobs.status = completed` 且存在以下信号之一：

  * `artifacts/jobs/<job_id>/run_meta.json`（或 `result.json` meta）里：

    * `answer_truncated == true`
    * 或 `answer_saved == true && answer_id != ""`
  * answer 文本启发式：末尾出现未闭合 fence（```）、明显半句、或长度远小于 `answer_chars` 预期。

> 这类修复可以做到**纯本地读取**：优先走 `chatgpt_web_answer_get(answer_id)`，不需要打开 ChatGPT 页面，更不会发送 prompt。

### 触发条件 2：Answer artifact 缺失/路径不一致（自愈）

* `jobs.status = completed` 但 `jobs.answer_path` 指向文件不存在；
* 或 `answer.md/answer.txt` 并存但 DB path 缺失/不一致。

> 修复动作：调用 `chatgptrest/core/artifacts.py::reconcile_job_artifacts()`，属于本地文件操作。

### 触发条件 3：需要更强证据包自包含（incident 已发生但 driver debug 未收齐）

* 发现 `jobs.status in (blocked,cooldown,needs_followup)` 且相关 job_event / blocked_state 引用的 debug artifact 文件未在 incident pack 内。

> 修复动作：补拷贝证据文件，不触发 UI 操作。

---

## D-3：修复动作（按安全性从高到低排列；默认只启用前两项）

### 动作 A：Answer rehydrate（安全：纯本地文件读取）

* 条件：存在 `answer_id`，且 `answer_saved=true`，且当前 answer 明显短于预期
* 执行：

  1. 调用 driver 工具：`chatgpt_web_answer_get(answer_id, offset, max_chars)` 分片拉回全文

     * 注意：该工具在 `chatgpt_web_mcp/server.py` 中读取 `MCP_ANSWER_DIR/CHATGPT_ANSWER_DIR`，不访问 ChatGPT 网络。
  2. 将合并后的完整答案写回：

     * `chatgptrest/core/artifacts.py::write_answer()`（原子写）
  3. 更新 DB（需要 lease 吗？这里 job 已终态，建议新增一个“修复写入”接口，或用 `transition` 到同状态并更新字段的方式）：

     * 更新 `jobs.answer_path/answer_sha256/answer_chars`（如有字段）
     * 插入 job_event：`answer_repaired`，payload 包含 old/new sha256、chars、repair_type=rehydrate

### 动作 B：Conversation export 对账修复（中等风险：会调用 export，但不发送 prompt）

* 条件：没有 answer_id 或 answer_id 不可用，但 job_dir 里已有 `conversation.json` 或可安全 export 一次
* 执行：

  1. 若本地已有 `conversation.json`：直接用 `worker._extract_answer_from_conversation_export()` 的同等逻辑抽取 candidate
  2. 若没有 export：

     * 先检查 blocked_state：若 blocked → **跳过**（避免触发 Cloudflare）
     * 否则调用 `chatgpt_web_conversation_export` 一次（全局限频，见降噪）
  3. 若 candidate 满足 `_should_prefer_conversation_answer()`：写回 answer（原子写）并写 event `answer_repaired_from_export`

> 说明：这一步仍然是“无 prompt side-effect”，但会打开/访问会话页面或 backend-api，有潜在 Cloudflare 风险，所以默认应全局限频 + blocked 时跳过。

---

## D-4：落盘路径（状态、日志、证据）

### daemon 状态

* `state/repair_daemon_state.json`

  * `last_scan_ts`
  * per job 的 `next_try_ts`、`fail_count`、`last_repair_sha256`（用于降噪与去重）

### daemon 日志

* `artifacts/monitor/repair_daemon/repair_YYYYMMDD.jsonl`

  * 记录每次扫描的统计（发现多少候选、处理多少、成功/失败原因分布）
  * 每个 job 的修复动作写一条结构化日志：`{job_id, action, ok, elapsed_ms, before_sha, after_sha, reason}`

### 修复前后证据（可选但很实用）

* `artifacts/monitor/repair_daemon/jobs/<job_id>/`

  * `before_answer_preview.txt`（前 2k 字）
  * `after_answer_preview.txt`
  * `repair_manifest.json`（包含触发条件、修复动作、sha256/长度变化、调用了哪些 driver 工具）

---

## D-5：如何降噪（避免刷屏/重复修复/无效重试）

* **幂等修复**：以 `before_sha256 + repair_type` 作为去重键

  * 若某 job 在同样 `before_sha256` 下已修复成功一次，则不再重复修复。
* **指数退避**：对失败的 job：

  * `fail_count=1`：5 分钟后重试
  * `fail_count=2`：30 分钟后
  * `fail_count>=3`：24 小时后或人工介入
* **每轮限额**：

  * 每轮最多处理 N 个 job（例如 5），避免异常时“修复风暴”。
* **全局限频**（尤其 export 相关）：

  * 类似 `worker._throttle_chatgpt_sends` 的机制，但 key 用 `repair_export`：

    * 例如每 2~5 分钟最多一次 export（全局），或者按 host/IP 限制更保守。

---

## D-6：如何避免制造风控风险（最重要）

* **硬性约束：永不调用 send/prompt 工具**

  * repair daemon 只能调用：

    * `chatgpt_web_answer_get`（本地读）
    * `chatgpt_web_idempotency_get`（本地查）
    * `chatgpt_web_blocked_status`（状态读取）
    * （谨慎）`chatgpt_web_conversation_export`（不发 prompt，但要限频 + blocked 时跳过）
  * 明确禁止：`chatgpt_web_ask`、任何会触发 `_chatgpt_send_prompt()` 的路径。
* **blocked 时降级**

  * 一旦 blocked_state 显示 blocked/cooldown：

    * 只做“纯本地修复”（answer_get、artifact reconcile）
    * 不做 export、不做 capture_ui（除非 incident 采证需要且你明确允许）
* **并发为 1**

  * repair daemon 默认单线程单并发，避免打开多个 page/触发 driver tab limit 或 Cloudflare。
* **可审计**

  * 每次动作必须落 `job_event`（`answer_repaired*`），并写 daemon jsonl，方便后续审计“有没有可能误操作”。

---

如果你愿意把 D 的 repair daemon 做到“更闭环”，下一步就是：当 repair daemon 修复失败且重复失败（例如 3 次）时，自动在 `ops/maint_daemon.py` 的 incident 体系里写入一个 `category=repair_failed` 的 incident，并带上“需要人工介入”的指引（但仍不发送 prompt）。这样就能形成：**发现问题 → 自动修复 → 修复失败自动升级工单** 的运维闭环。
