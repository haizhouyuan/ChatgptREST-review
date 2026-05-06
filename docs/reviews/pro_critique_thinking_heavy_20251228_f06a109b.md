# Pro/Thinking Heavy 批判式审查（2025-12-28）

- job_id: f06a109b6c514559ad4c2de1ad13160b
- conversation_url: https://chatgpt.com/c/69511926-b584-8321-8db2-a3320d4bf32b
- idempotency_key: chatgptrest:pro_critique:20251228_114838Z:6ba9919e
- review_pack: /vol1/1000/projects/ChatgptREST/state/chatgpt-pro-packs/chatgptrest_code_review_pack_20251228_114757Z_35d266d.zip
- answer_artifact: /vol1/1000/projects/ChatgptREST/artifacts/jobs/f06a109b6c514559ad4c2de1ad13160b/answer.md

---

下面是**按 zip 内 `PRO_REVIEW_REQUEST.md` 的要求**给出的批判式静态审查输出（仅静态阅读，不运行任何代码/服务）。

---

## 1) 我已读到的关键文件（15 个路径）

1. `PRO_REVIEW_REQUEST.md`
2. `docs/handoff_chatgptrest_history.md`
3. `docs/runbook.md`
4. `chatgptrest/worker/worker.py`
5. `chatgptrest/executors/chatgpt_web_mcp.py`
6. `chatgptrest/core/job_store.py`
7. `chatgptrest/core/artifacts.py`
8. `chatgptrest/core/db.py`
9. `chatgptrest/core/idempotency.py`
10. `chatgptrest/api/routes_jobs.py`
11. `chatgpt_web_mcp/server.py`（重点扫了 Deep Research、wait 刷新、导出、tab limit、debug artifacts）
12. `ops/maint_daemon.py`
13. `ops/monitor_chatgptrest.py`
14. `ops/verify_job_outputs.py`
15. `tests/test_deep_research_classify.py`

---

## 2) 逐项核对：`docs/handoff_chatgptrest_history.md` 的历史问题是否覆盖 & 仍可能回归点

> 我按该文档列的 28 条“已发生过的真实故障/增强点”逐条对照了实现（重点在 worker/job_store/executor/driver/ops）。

### 1) Answer path 单一真相源 ✅

* 现状：DB 里落 `answer_path`，API `/answer`、preview 走该路径；`reconcile_job_artifacts` 会尝试把 `.staging.<lease_token>` 恢复到 canonical。
* 回归点：**COMPLETED 但文件落盘失败**仍可能出现（见后面的 P1 风险）。

### 2) Lease token + CAS + staged writes ✅

* 现状：`store_answer_result` 要求 `expected_lease_owner+token`，并 staged 写后 `replace`；`renew_lease` 心跳；`claim_next_job` 原子 claim。
* 回归点：**先 transition 再 replace**的顺序对崩溃/IO 异常敏感（P1）。

### 3) Cancel attribution ✅（但“定位是谁/哪个进程”仍偏弱）

* 现状：`/v1/jobs/{id}/cancel` 记录 UA、X-Client-*、X-Request-Id、client host/port，写入事件 `cancel_requested`，并在 QUEUED 时直接转 CANCELED。
* 回归点：**缺服务端/调用侧强关联标识**（比如 server hostname/pid、auth subject 的非敏感哈希、反向代理 request id 等），排障时可能仍“只能看到是某个客户端取消”。

### 4) Transient assistant errors 视为可重试 ✅

* driver（`chatgpt_web_mcp/server.py`）有 `_looks_like_transient_assistant_error`；executor（`chatgpt_web_mcp.py`）会把短错误当作 in_progress 继续 wait。
* 回归点：误判范围/语言覆盖不足（P2）。

### 5) answer_id rehydrate ✅

* executor 里 `_rehydrate_answer_from_answer_id` 分片拉取 `answer_get`，用于 tool 截断但后端存了 full blob 的场景。
* 回归点：rehydrate 触发条件依赖 meta 字段一致性，且有 max_total_chars 上限；如果 driver meta 变化容易失效（P2）。

### 6) Conversation export reconciliation + DOM export normalize ✅（但仍有选错答案风险）

* worker 有 `_normalize_dom_export_text` 修 “Copy code” 伪文本；`_extract_answer_from_conversation_export` 做问题匹配提取。
* 回归点：**多条 assistant 消息**（尤其 Deep Research）时提取策略可能永远拿到 ack（P0）。

### 7) UTF-8 chunking ✅

* `artifacts.read_text_chunk` 以文本切片，避免 byte offset 断 UTF-8。
* 回归点：每次读全文件再切片，对超长 answer/高并发拉取会有内存/IO 压力（P2）。

### 8) mihomo delay 快照 ✅

* worker 在 blocked/cooldown 相关路径会写 snapshot 到 artifacts + DB events。
* 回归点：抓不到/吞异常属于“尽力而为”，但这反而会导致关键现场缺失（P2）。

### 9) 两段式调度 send vs wait ✅

* `phase` 字段、`claim_next_job(phase_filter)`、`release_for_wait`、attempts 不在 wait 阶段消耗。
* 回归点：phase 写错或漏写会导致 attempts 逻辑偏移/队列饥饿（P2）。

### 10) 超时拆分 send vs wait ✅

* executor/worker 都体现：send 阶段拿不到 conversation_url 走可重试；wait 走 slicing。
* 回归点：send 阶段返回 in_progress 的语义需稳定，否则 worker 误判状态（P2）。

### 11) Wait 刷新 + export fallback ✅（但“跨 slice 的刷新频率”仍可能过高）

* driver wait：timeout/瞬断时最多 refresh 一次；worker：wait slicing 下会周期性 export。
* 回归点：**每个 slice 都可能 refresh 1 次**，长跑 job 仍可能累积很多刷新（P1）。

### 12) ops 支持 worker role ✅

* runbook 明确 send worker / wait worker。
* 回归点：实际部署脚本/服务文件不一致时易误配（P2）。

### 13) attachment send stuck guard ✅

* executor：send 阶段 in_progress 且无 conversation_url，给出 retry_after/not_before，依赖 idempotency 之后恢复。
* 回归点：若 idempotency 记录落得不稳定，可能反复 stuck（P1）。

### 14) driver 合并到仓库 ✅

* 现状已在 repo 内。
* 回归点：边界变薄后，Chrome/Tab 生命周期更重要（P1）。

### 15) driver tab limit + stats ✅

* server.py 有 semaphore 限制并返回 TabLimitReached cooldown。
* 回归点：tab 限制命中后的“恢复/释放”策略若泄漏，可能永久降速（P2）。

### 16) driver persistent state defaults ✅（实现存在，但运维一致性要盯紧）

* blocked_state 文件路径有默认与 env 覆盖；monitor/maint 也尝试对齐。
* 回归点：多处默认路径（`.run/` vs `state/driver/` vs legacy chatgptMCP）混用时会“看错文件”（P2）。

### 17) export cooldown + backoff ✅

* worker `_maybe_export_conversation`：OK cooldown、fail backoff、全局 min interval + per-job state。
* 回归点：默认全局 10s 对“多 job 并发 wait slicing”仍可能偏激进（P1）。

### 18) suppress fallback resend when idempotency says sent ✅（我认为仍需更硬的“只要 sent 就禁止 resend”证明链）

* 文档里提到 sent-guard；executor/worker 都尽量避免重复 send。
* 回归点：如果某条路径仍会 fallback 重新 ask，风险是 **重复发问/UI 风暴/风控**（P0/P1 视触发面）。

### 19) atomic worker JSON snapshots ✅

* worker 有 `_atomic_write_json` 等写法。
* 回归点：仍存在“事件写 DB 成功但文件写失败/反之”的双写不一致（P2）。

### 20) blocked-state 默认路径对齐 ✅（基本到位）

* monitor 会优先 env 或 `state/driver/`，否则 `.run/`。
* 回归点：help 文案仍叫 chatgptMCP state，容易误导（P2）。

### 21) soak helper ✅

* ops 下有 soak/monitor。
* 回归点：缺少“覆盖 Deep Research + slicing + export + refresh”组合场景的长期 soak 断言（P2）。

### 22) idempotency collision：file_paths 绝对/相对 ✅

* routes 里 `_canonicalize_chatgpt_web_input` 做了统一 resolve。
* 回归点：仍可能出现其它字段表现形式差异（空白/换行/列表顺序）导致“语义重复但 hash 不同”（P2）。

### 23) MCP wrapper 长轮询断连 ✅（只 retry once，可能不够）

* `McpHttpClient.call_tool` 遇错重建 session 重试一次。
* 回归点：长跑网络抖动可能需要更明确的 retry 分类（P2）。

### 24) 避免误判 needs_followup：“Answer now / Writing code” ✅

* executor 把该 marker 当 false positive，保持 in_progress + wait/export 恢复。
* 回归点：debug_text 来源/格式变化会导致规则失效（P2）。

### 25) health endpoint aliases + MCP 输入宽容 ✅

* API 有 `/healthz` `/health` `/v1/health`。
* 回归点：health 仅返回 ok，不检查 DB/driver/队列健康（P2）。

### 26) rescue follow-up race ✅

* worker `_looks_like_rescue_followup` + grace window：父 job 若刚完成则 short-circuit，避免重复 user 消息。
* 回归点：判定条件偏关键词，误判可能抑制合法 follow-up（P2）。

### 27) Deep Research：短 ack 被当 completed ✅（driver 侧已修，但 worker export 侧仍可能遗漏）

* driver 有 `_classify_deep_research_answer`（ack→in_progress、confirm→needs_followup）。
* 回归点：worker 用 export 兜底时的“答案提取策略”可能永远拿到 ack（P0）。

### 28) 离线 verifier ✅

* `ops/verify_job_outputs.py` 会产出 verify_report.json/md 并标注常见风险。
* 回归点：若不自动跑/不进 CI，很多质量回归只能靠人工发现（P2）。

---

## 3) 风险 / 遗漏清单（P0/P1/P2：严重级别 + 影响 + 触发条件 + 修复方向）

> 下面每条我都尽量对齐你们文档中的真实故障类型（重复发问、UI 风暴、截断、选错 answer、无法定位等）。

### P0-1：Deep Research + conversation export 兜底 **可能“永远选到 ack”导致无法 finalize**

* **影响**：Deep Research 场景下，如果 driver wait 因风控/渲染问题迟迟不给 completed，worker 试图靠 export 提前完成，但**提取逻辑可能一直拿到“第一条 assistant ack”**，从而：

  * job 可能长期 in_progress/反复 slicing；
  * 或错过“export 已有最终报告”的自愈窗口；
  * 最坏情况下触发更多 refresh/export，扩大风控风险。
* **触发条件**：export 里同一个 user question 后出现多条 assistant（典型：先 ack，再长报告）。当前 `_extract_answer_from_conversation_export` **优先取“匹配的 user 消息后紧跟的第一条 assistant”**；对 Deep Research 这往往就是 ack。
* **建议修复方向（不写代码版）**：

  1. 当 `deep_research_requested=True` 时，提取策略改为：在匹配到的 user 消息之后、下一个 user 消息之前，**遍历所有 assistant**，选择**最后一个满足 finalize 条件**（`_deep_research_export_should_finalize==True`）的候选；若都不满足，则返回 ack（继续等）。
  2. 额外加一个“报告特征优先级”：含 `目录/Table of contents/Research report/调研报告/Chapter 1/第一章` 等的候选权重更高（driver 侧其实已经有类似 body hint 的思路）。
  3. 对“长报告 + 后续短确认”反向场景，优先选**最长/最像报告**的那条，而不是“最后一条”。

---

### P0-2：重复发问/风控风险仍有“边缘路径”可能漏住（sent-guard 证据链不够硬）

* **影响**：一旦出现重复发送 prompt：

  * UI 侧会产生多条 user message（你们最怕的 UI 风暴）；
  * 61s 节流会被放大成队列阻塞；
  * 更容易触发 Unusual activity / network cooldown。
* **触发条件**：多 worker 并发 + reclaim + fallback preset/重试路径叠加时，若某条路径没有严格依赖 DB idempotency 的“已发送”事实，就可能 resend。
* **建议修复方向**：

  1. 把“是否允许 send side-effect”收敛成**一个唯一判定点**：只要 DB idempotency/driver state 标记为 sent，就**强制禁止再次 ask**（除非人为显式 override，并记录审计事件）。
  2. 在 job_events 增加一个不可变的 `prompt_sent_once` 证据：包含 idempotency_key、首次发送时间、worker_id、driver run_id（非敏感）、conversation_url。之后任何 resend 都必须显式写 `prompt_resend_override` 事件。

---

### P1-1：wait 刷新策略“单次很保守，但跨 slicing 可能累积过多 refresh”

* **影响**：refresh 是高风险动作（更像“活跃行为”），长期 job（Deep Research/长答）在 slicing 模式下，**每个 slice 都可能触发一次 refresh**，累计 refresh 次数不可控 → 风控概率上升。
* **触发条件**：driver wait 在 timeout/瞬断时最多 refresh 一次；但 worker 可能 60s slice 反复调用 wait。
* **建议修复方向**：

  1. 引入“跨 slice 的 refresh 冷却状态”，放到 `artifacts/jobs/<job_id>/wait_refresh_state.json` 或 DB rate_limits（类似 export throttle）：

     * 每个 conversation_url：例如 **10–15 分钟最多 refresh 1 次**；
     * 连续失败指数退避（10m→30m→2h…），并把刷新次数/原因落到 job_events。
  2. refresh 之前先判断“export 是否已有新增 assistant 或 answer 是否增长”，能不 refresh 就不 refresh。

---

### P1-2：`store_answer_result` 的“先 DB transition 再文件 replace”顺序对崩溃/IO 故障敏感

* **影响**：出现 `status=completed` 但 `answer_path` 文件不存在/不完整；虽然 `reconcile_job_artifacts` 会尝试用 `.staging.<lease_token>` 修复，但如果：

  * replace 失败且 staging 也写坏/丢失；或
  * lease_token 被清理/被覆盖；
    就可能留下一条“完成但无答案”的脏数据。
* **触发条件**：进程崩溃、磁盘满、跨文件系统 rename 异常、权限问题。
* **建议修复方向**：

  1. 更稳妥的两阶段提交：先写文件（staging→fsync/校验 sha），再写 DB（或在 DB 标记 `answer_committed=false/true`）；
  2. 或至少把 “replace 成功” 作为事件写入（`answer_file_committed`），并在 API 层遇到 completed 但文件缺失时返回清晰可重试错误 + 自动触发 reconcile。

---

### P1-3：conversation export 的全局节流默认 10s，遇到多 job wait slicing 可能仍偏激进

* **影响**：export 本身是 UI/网络动作；10s 全局最小间隔在“多 job 并行等待”下仍可能形成持续流量，叠加 refresh 风险。
* **触发条件**：大量 in_progress job + slicing + export 兜底开启。
* **建议修复方向**：

  1. 默认值更保守（例如 30–60s），或按 job 数动态调大；
  2. export 触发条件更“按需”：只有在 wait 超时且 UI 无新 assistant、或需要做 rehydrate/最终一致性校验时才 export；避免“只要 needs_followup/in_progress 就 export”。

---

### P2-1：/cancel attribution 对“定位是谁/哪个进程”仍不够

* **影响**：你能知道某个客户端取消了，但可能很难追到“哪个上游服务实例/哪个用户会话/哪个批处理脚本”。
* **触发条件**：多入口/多代理/多实例调用 cancel。
* **建议修复方向**：

  * 在不引入敏感数据前提下，增加：`server_hostname`、`server_pid`、`request_received_at`、`forwarded_request_id`（如有）、以及对授权主体做不可逆 hash（如果你们有稳定的 non-PII subject）。
  * 同时把这些写入事件 payload，方便串联日志。

---

### P2-2：answer chunk API 读全文件再切片，超长回答/高并发拉取时资源开销可能偏大

* **影响**：CPU/内存/IO 放大，尤其是客户端分片拉取频繁时。
* **建议**：改为按 offset 流式读取（字符边界可用增量 decoder 或按字节块扫描到合法 UTF-8 边界）。

---

### P2-3：driver debug artifacts 默认落在 debug_dir，job artifacts 不自包含

* **影响**：现场证据可能被清理/路径不一致，导致“无法复现/无法定位”。
* **建议**：把 screenshot/html/text **复制到 `artifacts/jobs/<job_id>/debug/`** 并记录相对路径到 job_events/run_meta。

---

## 4) Deep Research 专项回答（按你的 3) 两个问题逐条）

### 4.1 现在的 ack 判定规则是否足够鲁棒？还缺哪些句式需要覆盖？

你们当前做法（driver：`_classify_deep_research_answer`，worker：`_deep_research_export_should_finalize`）的核心是：

* **短文本**（≤1200）命中 ack regex → 视为 in_progress；
* 命中 confirm/多问句 → needs_followup（driver 才有这层）；
* 否则 completed。

我认为总体方向对，但仍有两类缺口：

**A) 更“口语化/轻量”的 ack**（很常见，但不一定包含“研究/报告”关键词）
建议补：

* 中文：

  * “我先去查一下/我查查资料/我整理下思路/我需要一点时间整理”
  * “我在梳理信息中/正在汇总要点/我马上回来给你结果”
  * “我先做个深挖/我先深挖一下/我先做个 deep dive”
* 英文：

  * “Let me look into this.” / “Let me dig into it.”
  * “I’m working on it.” / “Give me a moment.”
  * “I’ll compile a report.” / “I’ll share my findings shortly.”

**B) “半成品/提纲式”内容**
有时 Deep Research 会先吐一个“目录/大纲/计划”，长度可能 >1200，可能绕过 ack 判定，但它仍不是最终报告。
建议增加一个“提纲/计划/outline”特征检测（尤其在 deep_research=true 时）：

* 例如大量 bullet/章节标题但缺少正文、或出现“计划/我将按以下步骤/研究方法/接下来我会…”。
* 对这类内容，即使 >1200，也可以先标为 in_progress 或 needs_followup（视你们产品语义）。

---

### 4.2 如果 export 里同时存在“长报告 + 后续短确认”，怎样选取最终 answer（避免选错）？

这里我建议你们把“选 answer”做成一个**显式打分/筛选策略**，而不是“第一条/最后一条”的硬规则：

**推荐策略（适用于 export JSON 的 messages 列表）：**

1. 先定位“对应的 user 消息”索引 `u_idx`（你们已有基于全文匹配/前缀/公共前缀的 best_idx）。
2. 收集 `u_idx` 之后直到下一个 user 消息之前的所有 assistant 候选集合 `A = {a1,a2,...}`。
3. 对每个候选做分类：

   * 若 `deep_research=true`：先丢弃明显 ack/confirm（复用 driver 的 `_classify_deep_research_answer` 逻辑更一致）。
4. 在剩余候选里选 **最像“报告”的那条**：

   * 关键启发式：

     * 更长（chars 最大）；
     * 命中报告标记（目录/Research report/调研报告/Chapter/第一章/结论/参考等）；
     * 包含结构化段落（多标题、多引用、多表格/代码块且闭合）。
5. 若所有候选都被判为 ack/confirm，则返回 ack 并继续 wait（但要确保你们不会“永远卡住”——见 P0-1 的修复建议：应该能在后续候选出现时选到它）。

这样无论是：

* “ack → 长报告”（应选长报告），还是
* “长报告 → 短确认”（应选长报告），
  都不会被“第一条/最后一条”坑到。

---

## 5) wait 刷新 / 导出兜底（按你的 4) 两个问题逐条）

### 5.1 我建议的“最小刷新策略”（频率/上限/退避），以降低风控风险

你们 driver wait 内部“单次最多 refresh 一次”已经很保守；问题在于 **worker slicing 会把 wait 调很多次**。因此我建议把刷新变成“跨 slice 的全局策略”：

**建议默认参数（可按环境调）：**

* **每个 conversation_url / job：10–15 分钟最多 refresh 1 次**
* **总 refresh 上限**：例如每个 job 最多 3–5 次（超过后只 export 不 refresh）
* **指数退避**：

  * 第 1 次 refresh：wait timeout 后立即（你们已有）
  * 第 2 次 refresh：距离上次 ≥ 15 分钟
  * 第 3 次：≥ 60 分钟
  * 之后不再 refresh，只做 export/被动等待
* **刷新前置条件**（能减少不必要动作）：

  * 最近一次 export 没有新增 assistant；
  * UI 最后 assistant 文本长度在 N 分钟内无增长；
  * 没有处于 blocked/cooldown（否则 refresh 很可能“火上浇油”）。

**落地方式（不引入重依赖）：**

* 类似 `conversation_export_state.json`，新增 `wait_refresh_state.json`：记录 `last_refresh_at / consecutive_refresh_failures / cooldown_until / total_refreshes`。
* 或复用 DB 的 `rate_limits` 表，key 做成 `chatgpt_web_wait_refresh:<conversation_id>`。

---

### 5.2 如果必须更强兜底：建议落哪些证据、挂到哪里

你们当前 driver 会在 debug_dir 存 screenshot/html/text；worker 会存 conversation.json 到 job artifacts。还差两点：

**A) 证据应“以 job 为中心”自包含**
建议把这些都复制/汇总进 `artifacts/jobs/<job_id>/` 下：

* `debug/driver_wait_timeout_*.png|.html|.txt`（从 debug_dir copy 过来）
* `conversation.json`（已有）
* `conversation_export_state.json`（已有）
* `wait_refresh_state.json`（建议新增）
* `run_meta.json`（已有，但建议增加计数：export_attempts/refresh_attempts/tab_limit_hits 等）

**B) 证据要能从 API job view/result 直接定位**

* 在 `job_events` 里写结构化 payload：

  * `debug_artifacts_relpaths`: [`debug/...png`, `debug/...html`, `debug/...txt`]
  * `export_path`: `conversation.json`
  * `refresh_reason` / `export_reason` / `attempt_no`
    这样 ops 看 `/events` 或 artifacts 就能一键串起来，不用猜路径。

---

## 6) 运维与可观测性（按你的 5) 两个问题）

### 6.1 还缺哪些 health/metrics/logging（不引入重依赖前提下）

**Health（你们现在的 /health* 只返回 ok）建议至少加这些轻量检查：**

* DB：能否 `BEGIN IMMEDIATE` + 简单读写（避免 sqlite 锁死/只读挂载）
* artifacts_dir：是否可写（写一个临时文件立刻删）
* driver：

  * driver_mode=internal_mcp 时，能否调用一次轻量工具（例如 rate_limit_status / ping）
  * blocked_state 是否处于 cooldown（把原因/剩余秒数带出来）
* worker：最近一次 worker heartbeat（可以在 DB events 里写 `worker_heartbeat`，health 汇总“X 秒内是否出现过”）

**Metrics（可以先做 JSON，不用 Prometheus 也行）：**

* jobs 计数：按 status/phase 分布、队列长度、最老 queued 的 age
* lease：reclaim 次数、LeaseLost 次数
* send：send_throttled 次数、平均等待秒
* wait：wait slice 次数、每 job wait 总时长分位数（粗略即可）
* export：成功/失败次数、cooldown/backoff 命中次数
* refresh：触发次数、触发原因 topN
* tab limit：命中次数、最近一次命中时间

**Logging：**

* 你们已经把关键路径写到了 job_events + artifacts/events.jsonl，这很好。
* 建议补齐 “跨组件 correlation id”：把 driver 的 `run_id`、conversation_url、idempotency_key 的短 hash，统一写入 worker 的 run_meta 与 events，排障会快很多。

---

### 6.2 maint_daemon/monitor/soak/verifier 是否足够；缺什么会导致“无法复现/无法定位”

**我认为方向对，但“证据闭环”还差一口气：**

* `monitor_chatgptrest.py`：能持续 dump 事件 + 状态摘要，很适合作为“黑匣子”。

  * 建议：把 export/refresh/tab_limit/blocked_state 这几类关键信号做成单独 summary 段，避免淹没在海量事件里。

* `maint_daemon.py`：看起来更偏“事故管理 + proxy 侧健康”，对 blocked/cooldown 处理很关键。

  * 建议：当出现 blocked/cooldown/needs_followup 高频时，自动触发一次 job 级证据归档（把 driver debug artifacts copy 进 job）。

* soak：当前更多是“跑起来观察”。

  * 建议：加一个 Deep Research 场景 soak（长跑 + slicing + export + refresh），并在每轮结束自动跑 verifier。

* verifier：你们已经能离线检查 unbalanced fences / rehydration / export 相似度，这非常有价值。

  * 最大缺点：如果它不被定期跑/不进 CI，就很容易“回归了没人知道”。
  * 建议：最小化做法：maint_daemon 每天挑最近 N 个 completed job 跑一次 verifier，把报告写到 incident snapshot。

---

## 7) 回归建议：最关键的 pytest 用例清单（5–10 条）

我给你一个“优先级从高到低”的清单（其中不少你们仓库里看起来已经有雏形/同名测试，可以作为回归门禁；没有的我也写了应测点）：

1. **Deep Research export 选答正确性（P0）**

   * 构造 export messages：user 后有 assistant ack + assistant 长报告 + assistant 短确认
   * 断言：最终选中“长报告”，且 ack 不会导致永久等待/误完成。

2. **sent-guard：已发送绝不重复 send（P0/P1）**

   * 并发/重启/lease reclaim 情况下，确认同一 idempotency_key 只发生一次 ask side-effect。

3. **wait slicing 下 export throttle 生效（P1）**

   * 多次 slice 触发 export：验证 OK cooldown、fail backoff、global min interval 都会挡住风暴。

4. **wait timeout refresh 冷却（建议新增）（P1）**

   * 模拟连续 wait timeout：验证跨 slice 的 refresh 不会每分钟一次（需要你们实现 refresh_state 后再测）。

5. **staged write + reconcile（P1）**

   * 模拟完成时 canonical 缺失但 staging 存在：`reconcile_job_artifacts` 能恢复。

6. **attachment send stuck no conversation_url（P1）**

   * send 阶段返回 in_progress 且无 conversation_url：应进入可重试并最终通过 idempotency 恢复。

7. **cancel attribution 完整性（P2）**

   * /cancel 写入事件 payload，包含 headers/client 信息且不包含敏感头；同时确保 QUEUED→CANCELED 与 IN_PROGRESS→cancel_requested_at 的语义正确。

8. **transient assistant error 不被当 completed（P2）**

   * driver/executor 对 “Error in message stream / Attempting to reconnect” 等短错：应保持 in_progress 并触发一次恢复路径。

9. **idempotency collision：file_paths 相对/绝对等价（P2）**

   * 相同文件不同路径形式：canonicalize 后 hash 相同，不会误报 collision。

10. **verifier：export 与 answer 的相似度/截断修复（P2）**

* 构造截断 answer + export 完整：应提示 `tool_answer_truncated_not_rehydrated` 或通过 rehydrate/替换后消失。

---

### 最后一句（很直白的结论）

你们这套系统的“主干硬化”（lease/CAS、两段式调度、export backoff、Deep Research 分类、rescue follow-up guard、离线 verifier）已经把最常见的坑基本填上了；但**最大的 P0 仍然是“Deep Research + export 兜底时的选答策略”**——只要这个点选错，就会把“避免重复发问/避免 UI 风暴/避免截断”的总体目标反向拉爆，而且会制造极难定位的“看起来一直在等”的假死。

如果你愿意，我可以在不写业务代码的前提下，把“Deep Research export 选答”那套策略写成非常具体的伪代码/决策树，并对照你们现有函数边界（worker 的 `_extract_answer_from_conversation_export` / `_deep_research_export_should_finalize`，driver 的 `_classify_deep_research_answer`）给出最小侵入的改法。
