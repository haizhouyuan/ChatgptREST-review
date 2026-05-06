# ChatgptREST — Pro 代码审查（完整输出，2025-12-27）

- Source conversation: https://chatgpt.com/c/694ff03b-b6ac-8320-9d38-e940581ba825
- Captured from: artifacts/answers/bcb8f5aa87604f4c95fff5201964941e.md (driver offload)
- Note: artifacts/ is gitignored; this doc persists the review text.

---

## 我确实阅读到的关键文件路径（节选 6 条）

> 下面路径均来自你上传的 Markdown bundle 的“Included files”列表与正文标题，我在审查中会多次引用其中的具体函数/逻辑。

* `chatgptrest/core/job_store.py`
* `chatgptrest/worker/worker.py`
* `chatgptrest/executors/chatgpt_web_mcp.py`
* `chatgptrest/core/artifacts.py`
* `chatgptrest/core/idempotency.py`
* `docs/runbook.md`

---

## 架构与关键流程速写（用于定位问题）

从你给出的核心代码看，ChatgptREST 的关键“可靠性三件套”是：

1. **REST 层幂等（Idempotency-Key → job_id）**
   `chatgptrest/core/idempotency.py::begin()` + `chatgptrest/core/job_store.py::create_job()`：同 key 同 payload 返回同 job；同 key 不同 payload 409。

2. **DB Lease（SQLite jobs 表 lease_owner/lease_expires_at/lease_token）**
   `claim_next_job()` 原子 claim + `renew_lease()` 心跳续约 + 终态落库/写文件时用 `expected_lease_owner/token + require_lease_not_expired` 做 CAS，避免被回收后“旧 worker”仍写结果。

3. **两段式调度（phase=send/wait + worker role=send/wait）**
   `worker.py` 用 `role` 和 `job.phase` 决定 `exec_phase`，并在 **send 后把 job 放入 wait 阶段**（`release_for_wait()`），由 wait worker 只做收集不再“发新 prompt”。

此外，答案/导出大文件走 artifacts（`artifacts/jobs/<job_id>/answer.*`、`conversation.json`），并提供 UTF-8 byte offset chunk 读取（`artifacts.read_utf8_chunk_by_bytes()`），以及“导出对账/再hydrate”（`worker.py` 从 conversation export 抽取更完整 answer；`chatgpt_web_mcp.py` 从 answer_id 拉长文）。

这些机制整体方向是正确的，但在“**两段式 + lease reclaim + driver 切换**”的组合情形下，存在若干会导致 **堵塞、重复发送、worker crash、作业永久卡死** 的硬伤。

---

## P0 / P1 / P2 问题清单

> P0：会导致重复发问/作业永久卡死/worker 进程崩溃级联
> P1：会显著降低可靠性或造成误判/长尾故障，需要尽快修
> P2：偏工程质量、可运维性、可观测性/性能改进

---

# P0（必须优先修）

## P0-1：`attempts` 与 `max_attempts` 设计导致 **wait 阶段作业永久卡死**（尤其两段式必触发）

**涉及代码**：`chatgptrest/core/job_store.py::claim_next_job()`、`chatgptrest/worker/worker.py::release_for_wait()` 调度模式。

**影响**

* wait 阶段会被反复 claim（每次 claim 都会 `attempts = attempts + 1`），很容易触发 `attempts < max_attempts` 的门槛，导致作业**再也不会被任何 worker 领取**，表现为：

  * `status` 长期停在 `in_progress`（或 `cooldown`）
  * `phase` 可能是 `wait`
  * 但 worker 永远捞不到它（数据库里它“准备就绪”，却被 attempts 门槛挡死）
* 这会造成“队列看似不为空但 worker 空转”、以及客户端永远等不到 completed（严重运维事故）。

**触发条件**

* 典型必现路径（两段式最容易）：

  1. send worker claim → `attempts=1`
  2. send 返回 `in_progress` + conversation_url → `release_for_wait()`（phase=wait，lease 清空，但 status 仍是 `in_progress`）
  3. wait worker claim（仍会 `attempts++`） → `attempts=2`
  4. wait 可能再一次返回 `in_progress`（max_wait_seconds 到达、或者工具轮询没拿到最终 answer），worker 再 `release_for_wait()`
  5. 下一次 claim → `attempts=3`
  6. 默认 `CHATGPTREST_MAX_ATTEMPTS=3`（README 默认值）时，**下一次再想 claim 就失败**，作业永久卡死。

**修复建议**

* 把 `attempts` 的语义从“每次 claim 都算一次”改成更合理的：

  * **仅 send 阶段（phase=send）计入 attempts**；wait 阶段 claim 不应消耗 attempts（因为 wait 不会产生新副作用）
  * 并且 **wait 阶段不应被 `attempts < max_attempts` 限制**（否则即使 prompt 已发送、conversation_url 已存在，也会因为 attempts 达上限而“永远取不到答案”）。
* 最小改动方案：在 `claim_next_job()` 的 SELECT/UPDATE 条件里引入 `COALESCE(phase,'send')` 的条件分支：

  * `phase='wait'` 时跳过 attempts gate，并且 `attempts` 不自增
  * `phase!='wait'` 时保持现有行为

---

## P0-2：Executor/driver 调用异常未收敛，**任何网络/工具错误都可能直接把 worker 打崩**（lease reclaim 后可能重复执行）

**涉及代码**：

* `chatgptrest/executors/chatgpt_web_mcp.py::run()`（大量 `await asyncio.to_thread(self._client.call_tool, ...)` 未捕获 ToolCallError/Exception）
* `chatgptrest/worker/worker.py::_run_executor_step()`（`task.result()` 不做异常兜底）

**影响**

* 一旦 MCP HTTP 抖动、driver 返回错误、JSON-RPC 结构异常、或任何工具调用抛 `ToolCallError`/其它异常：

  * `executor.run()` 直接 raise
  * `_run_executor_step()` 的 `task.result()` 也会 raise
  * `worker.py::_run_once()` 没有全局 try/except，进程直接退出
* 进程退出 → lease 到期 → 作业被回收 → 另一个 worker 重跑：

  * **wait 阶段**：重复等待，浪费资源（还会触发 P0-1 attempts 问题）
  * **send 阶段**：如果 driver idempotency 状态不可用（见 P0-4），可能会**重复发送 prompt**（严重重复副作用）。

**触发条件**

* MCP server 短暂不可达 / HTTP 500 / SSE stream timeout / structuredContent 缺失（`mcp_http_client.py` 会抛 `McpHttpError` → `ToolCallError`）
* driver 工具本身抛异常
* 任何 executor 内部 bug（例如格式化 follow-up 等路径）未捕获异常

**修复建议**

* 双层兜底（建议两处都做）：

  1. 在 `ChatGPTWebMcpExecutor.run()` 内：对所有工具调用做 try/except，把异常收敛成 `ExecutorResult(status="cooldown" | "error", meta={"error_type","error","retry_after_seconds","not_before"})`，绝不能让异常冒泡到 worker。
  2. 在 `worker.py::_run_executor_step()`：对 `task.result()` 做兜底，保证 executor 即使抛异常也能被转成“可落库的失败结果”，worker 不崩。

---

## P0-3：lease 丢失窗口内写终态会抛 `LeaseLost`，当前实现会 **导致 worker 崩溃**（并可能引发重复）

**涉及代码**：

* `chatgptrest/core/job_store.py::store_answer_result()`、`store_error_result()`、`store_retryable_result()`、`store_canceled_result()` 都可能抛 `LeaseLost` / `AlreadyFinished`
* `chatgptrest/worker/worker.py` 在最终落库处基本不 catch（除了少数 release_for_wait）

**影响**

* 典型：executor 刚拿到 answer，准备 `store_answer_result()`，但 lease 在此刻过期或被回收：

  * `transition(... require_lease_not_expired=True ...)` rowcount=0 → 抛 `LeaseLost`
  * worker 没 catch → 进程崩
* 进程崩溃 → lease reclaim → 另 worker 继续跑：

  * 如果 prompt 已发送：重复等待
  * 如果仍处于 send 且 driver idempotency 不连续：重复发送风险

**触发条件**

* lease TTL 60s，虽然有 heartbeat，但当 DB 写锁拥塞、或 event loop 被阻塞、或系统卡顿，都可能出现续租不及时
* 多 worker 并发/运维重启导致 lease 被其他实例拿走
* 任何落库路径上的慢操作（例如文件系统异常导致 store_answer_result 延迟）

**修复建议**

* 在 worker 最终落库区域，对 `LeaseLost` / `AlreadyFinished` 做显式捕获：

  * `LeaseLost`：直接停止本次处理（另 worker 已接管），**不要崩溃**；可记录一个 `lease_lost_during_finalize` 事件用于排障
  * `AlreadyFinished`：视为幂等成功（另 worker 已完成），也不要崩溃
* 可选：把 finalize 前再做一次 `renew_lease()` 或检查 lease_expires_at 剩余时间，若不足则先续租再写结果（降低窗口概率）。

---

## P0-4：driver 切换/回滚期间的幂等连续性不足，可能导致 **同一 job 被重复发送**（尤其在“send 已发生但 conversation_url 未落库”的崩溃窗口）

**涉及代码/设计点**：

* `worker.py` 每次从 `cfg.driver_mode/cfg.driver_url` 构建 tool caller（`driver/factory.py`），作业不“绑定”到特定 driver backend
* `chatgpt_web_mcp.py` 的 driver-side idempotency key 为 `chatgptrest:{job_id}:{preset}`，其状态**依赖 driver 的 idempotency DB**（外部 chatgptMCP vs 内部 driver vs embedded 很可能各自独立）

**影响**

* 在 send 阶段，如果 prompt 已发送，但 worker 在 `set_conversation_url()` / `release_for_wait()` 前崩溃，DB 里可能仍没有 conversation_url。
* 之后如果你按 runbook 切换了 `CHATGPTREST_DRIVER_MODE`（external ↔ internal ↔ embedded），新 backend 上 **同样的 idempotency_key 未必存在**：

  * worker 重跑 send 时可能会认为“没发过”，从而**再次发送同样的用户消息**
  * 造成会话里出现重复 user message（成本/体验/正确性都很差）

**触发条件**

* 运行中切换 driver mode 并重启 worker（runbook 明确支持这种操作）
* driver idempotency DB 路径变化或被清理（例如 `.run/mcp_idempotency.sqlite3` 被删）
* send 阶段崩溃窗口（尤其在网络抖动/工具异常导致 worker crash 的情况下，见 P0-2）

**修复建议（强烈建议做“作业绑定 backend”）**

* 从系统安全角度，“切 backend”应该是**新作业走新 backend，旧作业继续走旧 backend**，直到 drain 完成。
* 落地方式（代码层）：在 jobs 表增加 `driver_mode` / `driver_url`（或至少 `driver_backend_id`），在 **job 创建时或首次 claim 时写入**，此后处理该 job 统一使用该字段，而不是实时读取 env。
* 运维侧补救（runbook）：切换前强制检查是否存在“send phase 且 conversation_url 为空”的 in_progress 作业；若有，禁止切换或先人工处置。

---

# P1（重要但不一定立刻炸）

## P1-1：`idempotency.begin()` 非原子（SELECT→INSERT），缺少 IntegrityError 兜底，存在并发竞态与“永久坏 key”的风险

**涉及代码**：`chatgptrest/core/idempotency.py::begin()`，`chatgptrest/core/job_store.py::create_job()`

**影响**

* 如果 API 层没有强制 `BEGIN IMMEDIATE` 串行化（你 bundle 未包含 API 实现，我无法确认）：并发请求可能出现：

  * 两个线程同时 SELECT 未命中 → 同时 INSERT → 一个报 sqlite IntegrityError
  * 若异常未被正确映射为“返回已有 job_id”，客户端可能收到 500
* 更糟的是：如果 idempotency 记录插入成功，但 job 插入失败且不在同一事务里，会出现 `idempotency record points to missing job` 的永久坏状态。

**触发条件**

* 并发重复提交（最典型就是客户端 retry）
* API 层未包事务或事务边界不一致
* 磁盘/DB 错误导致 job insert 失败

**修复建议**

* 在 `begin()` 内部改成“先 INSERT，失败再 SELECT”或 `INSERT OR IGNORE` + SELECT，并捕获 `sqlite3.IntegrityError`：

  * 保证 begin 本身在无事务情况下也安全
* 并明确要求 create_job 全程在一个事务里（DB + idempotency + job_events），artifact 写入失败也不要让事务处于不一致状态（见 P1-2）。

---

## P1-2：作业创建阶段 artifacts 写入不是 best-effort，可能把“已入库的作业”变成“API 返回失败但实际上存在”

**涉及代码**：`chatgptrest/core/job_store.py::create_job()` 里直接调用 `artifacts.write_request()`、`append_event()`，无 try/except。

**影响**

* 如果 artifacts_dir 权限/磁盘满/临时 IO 错误：

  * create_job 可能抛异常
  * 但 idempotency 记录和 jobs 行可能已经写入（取决于事务边界）
  * 客户端重试会拿到同 job_id（幂等），但第一次返回失败导致“客户端认为没成功”
* 这会制造大量“幽灵作业”（实际存在但调用方不知道/重复排查）。

**触发条件**

* artifacts 目录不可写、磁盘满、inode 用尽
* 临时 IO 抖动

**修复建议**

* 将 artifacts 写入降级为 best-effort：

  * DB 事务成功优先；artifact 写失败记录 event + 继续返回成功
  * 或者将 artifacts 写入放到事务提交后，并捕获异常（保证 API 语义一致）。

---

## P1-3：wait worker 默认可能长时间“占着一个 job 不放”（max_wait_seconds 默认 1800），导致 wait 队列吞吐不足，表现为“queued 堵塞”

**涉及代码**：`chatgptrest/executors/chatgpt_web_mcp.py::_wait_loop()`、`chatgptrest/worker/worker.py` 对 wait 角色不做切片

**影响**

* wait worker 单进程串行处理：一个 job 的 `_wait_loop` 可以跑到 `max_wait_seconds`（默认 1800s）
* 在高并发时，wait 队列会堆积，后面的作业即使已经有答案也拿不到，表现为队列“堵塞”

**触发条件**

* wait worker 数量少（最常见只起 1 个）
* 大量长回答/深度研究导致等待时间长
* driver wait 调用本身也可能长时间占用 tab/page 资源

**修复建议**

* “时间切片”策略：对 wait role 强制把单次 claim 的等待上限限制在一个较小 slice（例如 30~90 秒），超时就 `release_for_wait()` 让出 worker
* 或引入 `CHATGPTREST_WAIT_SLICE_SECONDS`（仅对 wait role 生效）
* 结合 P0-1 修复后，wait 重入不会耗尽 attempts，切片才真正可用。

---

## P1-4：send throttle 在“确认会发送之前”就占用配额，遇到 preflight blocked/工具失败会造成不必要的发送间隔浪费（放大 queued 堵塞）

**涉及代码**：`chatgptrest/worker/worker.py::_throttle_chatgpt_sends()` 在调用 executor 前就 try_reserve
而 `chatgpt_web_mcp.py` 里 preflight blocked_status 可能立刻返回 cooldown/blocked

**影响**

* 即使最终没有发送（blocked/异常/needs_followup），也会更新 `rate_limits.last_ts`，导致后续真实要发送的 job 被迫等待
* 在大量 blocked/cooldown 波动时，会把吞吐打得更低

**触发条件**

* Cloudflare 验证/blocked 状态频繁出现
* MCP/driver 抖动导致 send 工具调用失败

**修复建议**

* 把 throttle 尽量后移：至少先做一次轻量 preflight（blocked_status）确认“可以发送”后再 try_reserve
* 或在 executor 返回“未发送”的明确证据时，允许“回滚/补偿”last_ts（SQLite 上实现较麻烦，但可以用独立 key 或写入更谨慎）。

---

## P1-5：Pro fallback 可能在“已发送但 timeline 未标记 sent”的边缘情况下重复发送第二条消息

**涉及代码**：`chatgptrest/executors/chatgpt_web_mcp.py` fallback 逻辑依赖 `_is_sent(debug_timeline)`

**影响**

* fallback 会改用 `fb_key = chatgptrest:{job_id}:{fb}` 再 ask 一次
* 若第一次其实发送成功但 debug_timeline 未包含 sent/user_message_confirmed，则可能发送重复 user message（不同 preset 但内容同 question）

**触发条件**

* driver 的 debug_timeline 不稳定/字段变化
* unusual_activity/blocked 与发送确认阶段交织

**修复建议**

* fallback 前额外增加判据：

  * 若 result 已返回 `conversation_url`，优先认为“可能已发送”，改走 wait（或 `chatgpt_web_wait_idempotency` / `idempotency_get` 二次确认）
  * 或调用一次 `chatgpt_web_idempotency_get(primary_key)` 看是否已有 conversation_url，再决定是否 fallback。

---

# P2（工程质量与可运维性）

## P2-1：`artifacts.resolve_artifact_path()` 允许绝对路径，和 contract “path 一律相对 artifacts_dir” 的安全模型不一致

**影响**

* 一旦 DB 被写入绝对路径（bug/迁移/人工修库），读取接口可能访问 artifacts_dir 之外的文件
* 属于安全硬化项

**触发条件**

* answer_path / conversation_export_path 被写成绝对路径（非预期）

**修复建议**

* 直接拒绝绝对路径，或至少要求绝对路径也必须在 artifacts_dir 之下（更一致）。

---

## P2-2：`events.jsonl` 并发追加可能产生交错写，且日志/产物缺少轮转与清理策略

**影响**

* 多 worker 同时写同一 job events（或 monitor log）时，极端情况下会出现行交错/半行
* artifacts 与 MCP_CALL_LOG 长期运行会无限膨胀

**触发条件**

* 多 worker 高并发
* 长期运行未清理

**修复建议**

* 优先依赖 DB 的 `job_events`（已存在索引），artifact 的 jsonl 仅作 best-effort
* 增加 maint/cron：清理超过 N 天的 `artifacts/jobs/*`、`.staging.*`、`mcp_calls.jsonl` 轮转等
* runbook 补充磁盘阈值与清理步骤。

---

## P2-3：rate limit 使用 `time.time()`，对系统时间回拨敏感（小概率）

**影响**

* 时间回拨可能导致短时间内发送间隔计算异常（过快或过慢）

**触发条件**

* 宿主机 NTP 大幅校时

**修复建议**

* 记录 epoch 时间是合理的（跨进程共享需要），但可额外做保护：如果检测到 `now < last_ts`，把 last_ts 当作 now 处理，避免长时间卡死。

---

# 具体补丁建议（按文件路径分组，可粘贴伪 diff）

> 下面是“最小侵入、优先消除 P0 风险”的改动建议。由于 bundle 未包含 API 层/`state_machine.py`，我把补丁限制在你提供的核心文件内，并尽量不引入大规模 schema 重构（但会给出可选增强）。

---

## 1) `chatgptrest/core/job_store.py`：修复 attempts 逻辑（P0-1）

目标：**wait 阶段不受 max_attempts 限制**，且 **wait 阶段 claim 不递增 attempts**。

````diff
diff --git a/chatgptrest/core/job_store.py b/chatgptrest/core/job_store.py
@@ def claim_next_job(...):
-    row = conn.execute(
-        """
-        SELECT job_id, status
-        FROM jobs
-        WHERE not_before <= ?
-          AND (? IS NULL OR COALESCE(phase, ?) = ?)
-          AND attempts < max_attempts
+    row = conn.execute(
+        """
+        SELECT job_id, status
+        FROM jobs
+        WHERE not_before <= ?
+          AND (? IS NULL OR COALESCE(phase, ?) = ?)
+          AND (
+            COALESCE(phase, ?) = 'wait'
+            OR attempts < max_attempts
+          )
           AND (
             status IN (?,?)
             OR (status = ? AND (lease_expires_at IS NULL OR lease_expires_at < ?))
           )
-        ORDER BY created_at ASC
+        ORDER BY not_before ASC, created_at ASC
         LIMIT 1
         """,
         (
             now,
             phase_filter,
             DEFAULT_PHASE,
             phase_filter,
+            DEFAULT_PHASE,
             JobStatus.QUEUED.value,
             JobStatus.COOLDOWN.value,
             JobStatus.IN_PROGRESS.value,
             now,
         ),
     ).fetchone()

@@ def claim_next_job(...):
-    changed = conn.execute(
+    changed = conn.execute(
         """
         UPDATE jobs
         SET status = ?, updated_at = ?, lease_owner = ?, lease_expires_at = ?, lease_token = ?, attempts = attempts + 1
         WHERE job_id = ?
           AND not_before <= ?
           AND (? IS NULL OR COALESCE(phase, ?) = ?)
-          AND attempts < max_attempts
+          AND (
+            COALESCE(phase, ?) = 'wait'
+            OR attempts < max_attempts
+          )
           AND (
             status IN (?,?)
             OR (status = ? AND (lease_expires_at IS NULL OR lease_expires_at < ?))
           )
         """,
         (
             JobStatus.IN_PROGRESS.value,
             now,
             worker_id,
             lease_expires_at,
             lease_token,
+            # NOTE: attempts 仅在非 wait 阶段才递增
+            # （SQLite 不支持引用 SET 里别名，所以重复写 COALESCE 表达式）
+            # 这里用 CASE WHEN... 代替固定 +1
+        ),
+    ).rowcount
+```

上面 diff 里 `attempts = attempts + 1` 需要替换成 CASE 版本（这是关键）。给出完整可粘贴的 SET 片段如下：

```diff
-        SET status = ?, updated_at = ?, lease_owner = ?, lease_expires_at = ?, lease_token = ?, attempts = attempts + 1
+        SET status = ?,
+            updated_at = ?,
+            lease_owner = ?,
+            lease_expires_at = ?,
+            lease_token = ?,
+            attempts = attempts + CASE WHEN COALESCE(phase, ?) = 'wait' THEN 0 ELSE 1 END
````

以及对应参数列表需要多传一个 `DEFAULT_PHASE`（给 CASE 的 COALESCE 用）：

```diff
         (
             JobStatus.IN_PROGRESS.value,
             now,
             worker_id,
             lease_expires_at,
             lease_token,
+            DEFAULT_PHASE,
             job_id,
             now,
             phase_filter,
             DEFAULT_PHASE,
             phase_filter,
+            DEFAULT_PHASE,
             JobStatus.QUEUED.value,
             JobStatus.COOLDOWN.value,
             JobStatus.IN_PROGRESS.value,
             now,
         ),
```

这样改完后：

* wait-phase job 即使 attempts 达到 max 也能继续被 wait worker 捞到完成
* wait-phase claim 不会把 attempts 推高到 max，从根源消灭“卡死”。

---

## 2) `chatgptrest/executors/chatgpt_web_mcp.py`：工具调用异常收敛为 ExecutorResult（P0-2）

目标：**任何 ToolCallError/Exception 不得冒泡出 run()**。

建议增加一个内部 helper（示意）：

```diff
diff --git a/chatgptrest/executors/chatgpt_web_mcp.py b/chatgptrest/executors/chatgpt_web_mcp.py
@@ class ChatGPTWebMcpExecutor(BaseExecutor):
     async def run(...):
+        async def _safe_call_tool(*, tool_name: str, tool_args: Dict[str, Any], timeout_sec: float) -> Dict[str, Any]:
+            try:
+                return await asyncio.to_thread(
+                    self._client.call_tool,
+                    tool_name=tool_name,
+                    tool_args=tool_args,
+                    timeout_sec=float(timeout_sec),
+                )
+            except ToolCallError as exc:
+                return {
+                    "status": "cooldown",
+                    "error_type": "ToolCallError",
+                    "error": str(exc),
+                    "retry_after_seconds": 60,
+                    "not_before": _now() + 60.0,
+                }
+            except Exception as exc:
+                return {
+                    "status": "cooldown",
+                    "error_type": type(exc).__name__,
+                    "error": str(exc),
+                    "retry_after_seconds": 60,
+                    "not_before": _now() + 60.0,
+                }

@@
-            result = await asyncio.to_thread(
-                self._client.call_tool,
-                tool_name=tool_name,
-                tool_args=tool_args,
-                timeout_sec=float(send_timeout_seconds),
-            )
+            result = await _safe_call_tool(tool_name=tool_name, tool_args=tool_args, timeout_sec=float(send_timeout_seconds))

@@
-                wait_res = await asyncio.to_thread(
-                    self._client.call_tool,
-                    tool_name="chatgpt_web_wait",
-                    tool_args={...},
-                    timeout_sec=float(remaining) + 30.0,
-                )
+                wait_res = await _safe_call_tool(
+                    tool_name="chatgpt_web_wait",
+                    tool_args={...},
+                    timeout_sec=float(remaining) + 30.0,
+                )
```

注意点：

* 这会把“工具层异常”转成 `cooldown`，worker 会进入 `store_retryable_result()` 或 `release_for_wait()` 流程，而不是崩溃。
* 如果你更倾向把不可恢复错误直接变为 `error`，可按异常类型区分（例如结构性解析错误 → error，网络抖动 → cooldown）。

---

## 3) `chatgptrest/worker/worker.py`：兜底 executor 异常与 finalize 的 LeaseLost（P0-2/P0-3）

### 3.1 `_run_executor_step()` 对 `task.result()` 做兜底

```diff
diff --git a/chatgptrest/worker/worker.py b/chatgptrest/worker/worker.py
@@ async def _run_executor_step(...):
-        return task.result(), None
+        try:
+            return task.result(), None
+        except Exception as exc:
+            # 任何 executor 异常都必须收敛，避免 worker 进程崩溃导致 lease reclaim/重复执行
+            meta = {
+                "error_type": type(exc).__name__,
+                "error": str(exc),
+                "retry_after_seconds": 60,
+                "not_before": time.time() + 60.0,
+            }
+            return ExecutorResult(status="cooldown", answer=f"{type(exc).__name__}: {exc}", answer_format="text", meta=meta), None
```

> 这里需要 `import time` 已在文件顶部；`ExecutorResult` 已 import。

### 3.2 在 `store_answer_result/store_error_result/store_retryable_result/store_canceled_result` 调用处捕获 `LeaseLost/AlreadyFinished`

以 completed 分支为例：

```diff
@@ if getattr(result, "status", None) == "completed":
-            with connect(db_path) as conn:
-                conn.execute("BEGIN IMMEDIATE")
-                store_answer_result(...)
-                conn.commit()
+            try:
+                with connect(db_path) as conn:
+                    conn.execute("BEGIN IMMEDIATE")
+                    store_answer_result(...)
+                    conn.commit()
+            except LeaseLost:
+                # 另一个 worker 已接管/lease 已回收：不要崩溃；让对方完成最终落库
+                try:
+                    artifacts.append_event(artifacts_dir, job.job_id, type="finalize_lease_lost", payload={"when": "store_answer_result"})
+                except Exception:
+                    pass
+                return True
+            except AlreadyFinished:
+                return True
```

其它落库分支同理：

* 任何 finalize 时的 LeaseLost 都不应导致 worker 退出
* 记录一个事件即可

---

## 4) `docs/runbook.md`：补充“安全切换 driver”的前置检查与排障（P0-4）

给 runbook 增加一段**切换前检查**（示意文本，可直接粘贴进文档）：

````diff
diff --git a/docs/runbook.md b/docs/runbook.md
@@
 ## Start / Restart
@@
 - Rollback to external chatgptMCP (no code change):
   - set `CHATGPTREST_DRIVER_MODE=external_mcp` and `CHATGPTREST_DRIVER_URL=http://127.0.0.1:18701/mcp`
   - restart the workers (send/wait) to pick up the change

+## Driver Cutover Safety Checklist (避免重复发送)
+
+在切换 `CHATGPTREST_DRIVER_MODE/URL` 之前，务必确认不存在 “send 阶段进行中但 conversation_url 仍为空” 的作业。
+这种作业如果在切换后被重跑 send，可能因 driver-side idempotency 状态不连续而重复发送 prompt。
+
+建议在切换前执行（示例，需按实际 sqlite 路径调整）：
+
+```bash
+sqlite3 state/jobdb.sqlite3 "
+SELECT count(*) AS risky
+FROM jobs
+WHERE kind='chatgpt_web.ask'
+  AND status='in_progress'
+  AND COALESCE(phase,'send')='send'
+  AND (conversation_url IS NULL OR trim(conversation_url)='');
+"
+```
+
+若 risky > 0：
+1) 优先等待 send worker 恢复并落库 conversation_url；
+2) 或人工将这些作业标记为 needs_followup（避免自动重发）；
+3) 再进行 driver 切换。
````

---

# 测试与验证建议（pytest + 运行步骤）

> 你要求“pytest + 运行验证”，我按 **可在纯单元测试环境跑**（不依赖真实 ChatGPT/Chrome/MCP）的方式设计；同时给出一套手工/集成验证步骤。

---

## A. pytest 单元测试建议

### A1. 覆盖 P0-1：wait 阶段 attempts 不应卡死

新建 `tests/test_claim_next_job_attempts.py`（示意）：

* 准备临时 sqlite DB（用 `tmp_path`）
* 手工插入一条 wait-phase job：

  * `status='in_progress'`
  * `phase='wait'`
  * `attempts=max_attempts`
  * `lease_expires_at IS NULL`（模拟 `release_for_wait` 后的状态）
  * `not_before=0`
* 调用 `claim_next_job(... phase='wait')`
* 期望：

  * 仍能 claim 到 job（修复前会拿不到）
  * 且 `attempts` 不应增加（修复前会 +1）

同时再测：send-phase job 在 attempts 达上限时应不可 claim。

### A2. 覆盖 P0-3：`store_answer_result` lease 丢失时 worker 不应崩

* 直接测试 job_store 层：

  1. 插入 job status=in_progress，lease_token=A，lease_owner=W，lease_expires_at=过去
  2. 调用 `store_answer_result(... require_lease_not_expired=True ...)` 应抛 LeaseLost（这是 job_store 合理行为）
* 再测试 worker 层兜底（需要你按补丁在 worker catch LeaseLost）：

  * 构造一个“ExecutorResult completed”，但在落库前把 lease_expires_at 改成过去
  * 期望 `_run_once` 不 raise（而是吞掉并返回 True）
  * 并写入一个 `finalize_lease_lost` 事件（可选断言）

### A3. 覆盖 UTF-8 byte chunking 的边界正确性（避免“拿回答不全/乱码”）

测试 `artifacts.read_utf8_chunk_by_bytes()`：

* 写入一个包含中英文 + emoji 的 answer 文件（如 `"你好🙂ABC世界\n"` 重复多次）
* 用 offset 逐字节扫过（特别挑在多字节字符中间的 offset）反复读取 chunk
* 断言：

  * 返回的 `start`（实际起点）永远不落在 continuation byte 上
  * 将 chunk 按 `next_offset` 拼接回去，得到的字符串应与原文一致（或至少是 UTF-8 合法且无丢字）

### A4. 覆盖 P0-2：executor 抛异常不应杀死 worker

* 写一个 DummyExecutor 的变体：`run()` 直接 raise RuntimeError
* 让 worker 领取 `kind=dummy.*` 或在 `_executor_for_job` 中注入（测试环境可 monkeypatch）
* 期望：worker 把 job 落到 `cooldown` 或 `error`（取决于你兜底策略），但不会让 `_run_once` 抛出异常。

---

## B. 运行验证步骤（手工/集成）

> 这些步骤偏“验证你关心的调度与重复发送风险”，不要求真实 ChatGPT 也能做一部分（dummy job），但与 chatgpt_web.ask 相关的重复发送只能在真实 driver 环境里观测。

### B1. 本地单机：验证两段式不会重复 send（基础）

1. 启动 API（按 README 习惯）
2. 启动 send worker 与 wait worker（分离角色）
3. 创建一个 `chatgpt_web.ask` job（带 Idempotency-Key）
4. 观察 `artifacts/jobs/<job_id>/events.jsonl` 与 `job_events`：应出现顺序类似

   * `claimed`（send）
   * （driver 调用事件你们在 driver 侧可能另有日志）
   * `wait_requeued` / `phase_changed send→wait`
   * `claimed`（wait）
   * 最终 `status_changed → completed`
5. 验证“无重复发送”的核心证据：在 driver/ChatGPT UI 的会话里只有一条对应的 user message；并且 job 的 `conversation_url` 一直指向同一会话。

### B2. 故障注入：send worker 在“已发送但未 release_for_wait”前崩溃

目的：验证 P0-2/P0-4 修复前后的差异。

* 方法：在 send worker 进程里人为制造 crash（例如在 executor 返回后、落库前插入 `os._exit(1)` 的临时代码，或用信号 kill）
* 预期（理想）：

  * job 之后被回收，新的 worker 重跑 **不会发送第二条消息**
  * 能从 idempotency_get 或已有 conversation_url 恢复并进入 wait

若你同时做“driver backend 绑定”修复（P0-4），还要验证：

* 即便你把 `CHATGPTREST_DRIVER_MODE` 切到另一个 backend，旧 job 仍使用原 backend 继续跑（直到完成）。

### B3. 验证 P0-1 修复：长等待/多次 requeue 不应耗尽 attempts

* 设置一个让 wait 很难完成的场景（例如人为让 wait_timeout_seconds 很短、max_wait_seconds 很小，迫使多次 `release_for_wait`）
* 观察：

  * 修复前：attempts 迅速达到 max_attempts，job 永久卡在 `in_progress`/`wait`
  * 修复后：attempts 不再被 wait 消耗，job 可持续被 wait worker 领取并最终完成。

### B4. 验证“拿回答不全”的三重保险链路

对一个会产生长回答的 job：

1. 看 executor meta 是否出现：`answer_truncated / answer_saved / answer_id`
2. 若 tool 输出被截断：

   * `chatgpt_web_mcp.py` 会尝试 `_rehydrate_answer_from_answer_id()`
3. 若仍不完整：

   * worker 会在 completed 后导出 conversation，并用 `_extract_answer_from_conversation_export()` 进行对账替换
4. 最终通过 `/answer?offset=&max_chars=` 分段拉取，拼接应完整无乱码（UTF-8 byte chunking）

---

## 额外建议：把“可靠性断言”变成可观测指标（非必须，但非常推荐）

为了让“是否重复发送/是否堵塞/是否 lease reclaim 频繁”变得一眼可见，建议在 job_events 里加入几个强信号事件（你已有体系）：

* `send_started` / `send_confirmed`（driver 返回 timeline 时记录）
* `send_replayed_suspected`（当 reclaimed 且 phase=send 且 conversation_url 为空时，直接标 needs_followup，并记录原因）
* `attempts_incremented`（仅 send 阶段）与 `wait_slice_requeued`（wait 切片）
* `finalize_lease_lost`（P0-3 修复后用于排障）

这些事件能极大提升 runbook 的可操作性。

---

## 附：本次审查依据（你上传的 bundle）
