下面给出**“终极推荐方案（single best plan）”**：以你评审包里已经冻结的 **REST v1 contract（docs/contract_v1.md）**、现有 **tool registry snapshot（tests/test_mcp_tool_registry_snapshot.py）**、以及 **maint_daemon/repair 的护栏思路（docs/maint_daemon.md + code/maint_daemon.py + code/repair.py）** 为基底，做一次“可维护/可扩展/可审计互信”的架构重整。目标是：**一次性把体系结构定型**，实现方式用**分阶段门禁**保证“功能全覆盖 + 行为兼容 + 可回滚”。

---

## 1) 最终目标架构（chatgpt_web_mcp 与 chatgptrest 两侧）

### 1.1 总体链路与边界（必须保留的稳定接口）

**稳定接口 ①：ChatgptREST v1 HTTP API（外部 contract，默认不得破坏）**

* 完全遵循 `docs/contract_v1.md`：`POST /v1/jobs`、`GET /v1/jobs/{id}`、`/wait`、`/answer`、幂等语义、conversation single-flight、send/wait phase、三条链路（chatgpt/gemini/qwen）全部兼容。
* 任何新增能力必须**只增不改**（加字段/加 endpoint），且对旧客户端保持同样行为。

**稳定接口 ②：Driver MCP Tools contract（ChatgptREST ↔ chatgpt_web_mcp）**

* 你已经有 **tool registry snapshot**（`test_mcp_tool_registry_snapshot.py`）来锁住“工具集合与参数”。终局形态要把它升级为：

  * **工具清单 + 参数 schema + 关键输出 envelope schema** 三件一起冻结
  * **capabilities handshake**：driver 启动后提供 `driver.describe`（或复用已有工具，但返回 schema_hash/version），ChatgptREST 在 worker 启动时校验一致性，不一致直接 fail-closed（拒绝发送 prompt）。

**稳定接口 ③：State/Artifacts contract（可审计互信的根）**

* 以 `docs/contract_v1.md` 里 “path 为 ARTIFACTS_DIR 下相对路径” 为硬约束。
* 明确稳定的 artifacts 目录结构（你现有 worker/repair/maint 已经默认在 `artifacts/jobs/<job_id>/...` 写入），终局要把它**结构化、版本化、可校验**（第4节会给“必须冻结的可执行约束”）。

---

### 1.2 终局目录/模块划分（单向依赖、可插拔、可审计）

我建议把 repo 明确成 **三个包层级**（一个共享 contracts + 两侧主包），并强制单向依赖：

#### A) 共享层：`chatgpt_contracts/`（新增，最关键）

目标：把“互信”变成可执行约束，而不是靠约定。

包含：

* `contracts/rest_v1.py|.json`：JobStatus/Phase/字段约束（与 `docs/contract_v1.md` 对齐，测试驱动）
* `contracts/mcp_tools_v1.json`：工具 schema 快照（包含输出 envelope 的关键字段）
* `taxonomy/errors.py`：统一 error_type/reason_type 分类与映射（worker/maint/repair/driver 共用）
* `taxonomy/events.py`：统一事件类型 + payload schema（DB events 与 artifacts events.jsonl 同构）
* `paths.py`：state/artifacts 的根路径与相对路径规则（防止路径漂移）

依赖方向：
`chatgptrest` → `chatgpt_contracts`
`chatgpt_web_mcp` → `chatgpt_contracts`
**共享层不得反向依赖任何一侧**。

---

#### B) Driver 侧：`chatgpt_web_mcp/`（UI 自动化与 MCP 工具服务）

> 评审包里能看到：driver 已经开始拆模块（`chatgpt_web_mcp.runtime.* / playwright.* / providers.* / mcp_registry` 等在 code/qwen_web.py、code/core.py、code/_tools_impl.py import 里出现），但仍存在全局状态与“工具命名混杂”（比如 `chatgpt_web_tab_stats` 实际返回 chatgpt/gemini/qwen 三者）。终局要把这些变成清晰分层。

**终局模块层次：**

1. `chatgpt_web_mcp/server/`

* `server_http.py`：FastMCP 启动、路由、健康检查、capabilities 输出
* 只负责进程生命周期，不做任何 UI 逻辑

2. `chatgpt_web_mcp/tools/`（稳定接口层：MCP 工具入口）

* 每个 tool 函数极薄：参数校验 → 权限/副作用护栏 → 调 provider adapter → 返回标准 envelope
* 工具分组（示例）：

  * `tools/chatgpt.py`: ask/wait/export/answer_get/self_check/capture_ui/blocked_status
  * `tools/gemini.py`: ask/wait/generate_image/self_check/capture_ui
  * `tools/qwen.py`: ask/wait/self_check/capture_ui
  * `tools/driver_admin.py`: tab_stats、rate_limit_status、version/describe

3. `chatgpt_web_mcp/providers/`（可扩展：每个网站一套 adapter）

* `ProviderAdapter` 接口（示意）：

  * `send(request)->SendResult`（**唯一允许“发送 prompt”**的入口）
  * `poll(request)->PollResult`（只读/轻副作用：刷新不应变更对话）
  * `export(conversation_url)->ExportResult`（只读）
  * `capture_ui(conversation_url,mode)->Snapshot`（只读）
  * `self_check(conversation_url)->SelfCheck`（只读）
* 三条链路分别实现：

  * `providers/chatgpt_web/*`
  * `providers/gemini_web/*`
  * `providers/qwen_web/*`（你包里 `code/qwen_web.py` 就是其主体雏形）

4. `chatgpt_web_mcp/playwright/`（底层能力）

* CDP 连接、页面打开、导航重试、证据采集（你已有 `playwright.cdp / navigation / evidence`）
* **不得包含“业务判断”**（比如深度研究 ack 判定、错误分类应上移到 taxonomy）

5. `chatgpt_web_mcp/runtime/`（跨工具共享、可测试）

* `config/env.py`：统一读 env，生成不可变 Config（避免现在多处散读）
* `paths.py`：state root、blocked_state、ratelimit file、ui snapshot base dir（你已有 runtime.paths）
* `locks.py`：单例锁、ask_lock（你已有 runtime.locks）
* `ratelimit.py`：_respect_prompt_interval（你已有 runtime.ratelimit）
* `idempotency.py`：tool 级幂等存储、answer blob 存取（worker 的 `chatgpt_web_answer_get` 依赖它：见 `code/worker.py:_rehydrate_answer_from_answer_id`）
* `concurrency.py`：tab semaphore（你已有 runtime.concurrency）
* `call_log.py`：审计日志（你已有 runtime.call_log）
* `answer_classification.py`：深度研究/ack/短答分类（你已有 `_classify_deep_research_answer`）

6. `chatgpt_web_mcp/compat/_tools_impl.py`（兼容层）

* 你现在的 `code/_tools_impl.py` 已经是“兼容 facade + 仍残留部分工具实现”。终局要求：

  * 只保留 **re-export / alias / thin wrapper**
  * 工具注册只通过 `mcp_registry`（或新 server 层），并由 snapshot test 锁死
  * 禁止在 compat 层继续堆业务逻辑（否则拆分永远停不下来）

**Driver 侧依赖方向（必须单向）：**
`server` → `tools` → `providers` → `playwright`
`tools/providers/playwright` → `runtime` → `chatgpt_contracts`
`compat` → `tools`（仅转发）
禁止 `providers` 反向 import `tools` 或 `server`。

---

#### C) ChatgptREST 侧：`chatgptrest/`（队列/幂等/风控/可观测/可自愈）

> 评审包里 `code/worker.py` 其实已经承担了：phase orchestration、completion guard、format_prompt 二次发送、conversation export reconcile、附件 zip 展开、自动提交 repair.autofix、以及大量事件写入。终局要把这些“横切逻辑”拆成可测试的模块，并把副作用路径收口到可审计的 guard。

**终局模块层次：**

1. `chatgptrest/api/`（外部 contract）

* FastAPI routes：只做请求校验、幂等键处理、入库、返回 JobView
* 严禁出现 UI/driver 调用、也不直接跑 worker

2. `chatgptrest/core/`（不依赖 worker/executors/ops）

* `config.py`：AppConfig（worker/repair/maint 全部从这里拿配置，而不是散读 env）
* `db.py`：连接策略、WAL/timeout、统一重试策略
* `job_store.py`：状态机与原子事务（lease/heartbeat/phase 切换、not_before、attempts 等）
* `artifacts.py`：统一写 answer/run_meta/events/manifest（现在 worker/repair/maint 都在各自 best-effort 写，终局要统一）
* `events.py`：写 DB event + artifacts event 的**同构**接口（第2节会解释这是“互信关键缺口”）
* `rate_limit.py`：send throttle（你 contract 已明确三条链路独立 key：chatgpt/gemini/qwen）
* `pause.py/incident_state.py`：全局/按 provider 暂停开关（fail-closed）

3. `chatgptrest/driver/`

* `api.py`：ToolCaller 抽象（你已有 `ToolCaller/McpHttpToolCaller/EmbeddedToolCaller` 的雏形）
* `capabilities.py`：启动时拉取 driver describe，校验 schema_hash（不一致 fail-closed）
* `errors.py`：ToolCallError → taxonomy 映射

4. `chatgptrest/providers/`

* `spec.py/policy.py/registry.py`（你已有 `code/registry.py`，非常接近终局）
* 统一：preset 归一化、min_interval、thread_url 校验、conversation 平台识别

5. `chatgptrest/executors/`（只关心“如何调用 driver”，不碰 DB）

* `chatgpt_web_mcp.py`（你已有，做得相对规范：idempotency_key=chatgptrest:{job_id}:{preset}，并有 blocked preflight）
* `gemini_web_mcp.py`（你已有：Drive 附件 pipeline + driver 调用）
* `qwen_web_mcp.py`（缺失于包，但应对齐同一接口）
* `repair.py`（你已有：SRE actions schema、drain guard、风险分级）
* **统一 ExecutorResult meta 结构**：`conversation_url/error_type/error/retry_after/not_before/_debug_timeline/...` 由 contracts/taxonomy 约束

6. `chatgptrest/worker/`（把现在的“大一统 run_once”拆成可测试组件）
   建议拆为：

* `worker_loop.py`：claim job + heartbeat + dispatch（非常薄）
* `stages/send_stage.py`：只负责 send 阶段：节流、blocked preflight、调用 executor.send
* `stages/wait_stage.py`：只负责 wait 阶段：poll、max_wait_seconds、in_progress backoff
* `guards/completion_guard.py`：deep research ack / min_chars / export_missing_reply downgrade（你已有逻辑，需模块化 + 测试）
* `guards/side_effect_guard.py`：所有“可能发送 prompt 的路径”统一入口（包括 format_prompt 二次发送）
* `reconcile/conversation_export.py`：answer ↔ conversation.json 对齐（你已有 `_extract_answer_from_conversation_export_obj` 与测试）
* `attachments/zip_expand.py`：ChatGPT zip 展开（现在在 worker 内，迁出）
* `autofix/submitter.py`：**只发事件/信号**，不直接开修（把“修复决策”收敛到 maint_daemon）
* `observability/markers.py`：prompt_sent / skipped_duplicate / assistant_answer_ready 等 marker 事件一次性写入（现在 worker 里散落 exists-check 写 event）

7. `chatgptrest/ops/`（把 maint_daemon 从脚本变成“可复用库”）

* `incidents/model.py`：IncidentState（你已有类似结构在 maint_daemon.py）
* `incidents/controller.py`：correlator + FSM（对应 docs/maint_daemon.md 的设计）
* `evidence/packer.py`：事故包落盘规范（manifest/summary/snapshots/actions.jsonl）
* `actions/executor.py`：重启/抓 UI/repair.check/codex analyze/autofix 的统一执行器（带预算与护栏）
* `codex/`：global memory、fingerprint、schema runner（你 maint_daemon/repair 两边都有，需去重）
* 入口脚本 `ops/maint_daemon.py` 只做 argparse + 调库

**ChatgptREST 侧依赖方向（必须单向）：**
`api` → `core` + `providers`
`worker` → `core` + `executors` + `providers` + `driver`
`executors` → `driver` + `providers` + `chatgpt_contracts`（禁止碰 DB）
`ops` → `core` + `driver` + `chatgpt_contracts`（禁止 import worker/api）
`core` → `chatgpt_contracts`
禁止出现 `chatgptrest` ↔ `chatgpt_web_mcp` 的交叉 import（只能通过 MCP contract/共享 contracts 交互）。

---

## 2) 除“大文件”外的核心问题清单（按严重度排序）

> 这里刻意不把“文件太大/需要拆分”当作问题本体（你已经有拆分计划 docs/refactor_large_py_split_plan_20260216.md）。只列**结构性/可靠性/互信**缺口。

### P0（会导致行为不兼容、风控风险、或互信不可审计）

**P0-1：Driver ↔ Server 的 contract 只锁了“工具名+参数”，没锁“关键输出语义”**

* 证据：目前 snapshot test（`test_mcp_tool_registry_snapshot.py`）仅能保证工具集合与参数形状不漂移。
* 风险：哪怕工具还在，输出字段/含义的微调也可能让 worker 的判断失真（例如 `retry_after_seconds/not_before/answer_id/done/next_offset`）。
* 典型脆弱点：

  * `chatgpt_web_answer_get` 的分块协议（worker 依赖：`code/worker.py:_rehydrate_answer_from_answer_id`）
  * `conversation_export` 返回 `export_path` 语义（worker 会 copy 并 reconcile）
* 终局修复：冻结 `ToolResultEnvelope` + per-tool 关键字段 schema，并在 worker 启动时 handshake 校验（不匹配 fail-closed：禁止 send）。

**P0-2：副作用路径（prompt send / 重启 / refresh/regenerate）缺少“统一的可执行护栏接口”，目前是分散约定**

* 证据：

  * worker 内的 format_prompt 是“第二次发送 prompt”（`code/worker.py` 里明确写了 best-effort send），其护栏依赖 `throttle_send=True` 与局部逻辑。
  * repair.autofix 声称“不发送新 prompt”，但允许 `refresh/regenerate/restart_*`（`code/repair.py`），护栏分散在 executor 内。
  * maint_daemon 也能触发重启/执行 codex 建议动作（`code/maint_daemon.py`）。
* 风险：未来拆模块/改调用链时，容易出现“本意只读却触发发送/重启”的误动作。
* 终局修复：引入统一 `ActionGuard` + `EffectBudget`（第5节给最终形态），任何副作用动作必须走同一入口记录审计与护栏决策；默认 fail-closed。

**P0-3：事件/错误 taxonomy 仍是“多处字符串约定”，导致触发器与复盘不可完全互信**

* 证据：

  * worker/maint/repair 都在用 `_looks_like_infra_error/_looks_like_ui_transient_error` 等启发式分类（worker 中 `_should_worker_auto_autofix`，maint 中 `_looks_like_infra_job_error`）。
  * issues_registry 里信号名混合了 `worker:*`、`driver:*` 的非强类型描述（`docs/issues_registry.yaml`）。
* 风险：

  * 同一类事故在不同模块里被分到不同类别 → 触发器不稳定（要么漏修，要么误修）。
  * audit 复盘时“为什么做了这个动作”无法用统一字段解释。
* 终局修复：把 taxonomy 升格为共享 contracts：

  * 标准化 `reason_type/error_type` 归一化与 severity
  * 标准化事件类型集合 + payload schema（DB events 与 artifacts events.jsonl 同构）

**P0-4：job 状态机的“关键事实”有一部分靠 debug timeline/启发式推断，而不是 DB 的一等字段**

* 证据：worker 里用 `_debug_timeline_has_phase(meta,"sent")` 或 “looks_like_thread_url” 推断是否进入 wait-phase（见 `code/worker.py` 里 `retry_phase="wait"` 的逻辑）。
* 风险：拆分/重构 meta 字段后，推断失败可能导致 **重复 send**（即使 driver 有 idempotency/duplicate guard，也会增加风控触发概率）。
* 终局修复：把“是否已发送用户消息/是否已确认 user message”变成 job_store 的稳定字段（例如 `prompt_sent_at/user_message_confirmed_at`），由 send-stage 原子写入，wait-stage 不再猜。

**P0-5：自愈闭环存在多入口（worker auto_autofix、maint_daemon infra healer、repair.autofix、codex_sre_autofix），存在“自激振荡”风险**

* 证据：worker 明确写了“默认 off，避免 double remediation”（`code/worker.py:_maybe_submit_worker_autofix`），但这说明风险真实存在。
* 风险：一旦同时开多个入口，可能出现：错误 → 重启 → 更多错误 → 更频繁重启（尤其 Chrome/CDP 抖动时），造成大面积 cooldown/blocked。
* 终局修复：**只保留一个决策中心**（maint_daemon 的 IncidentController），其他入口只产出信号/证据，不直接执行动作。

---

### P1（会显著降低可维护性/可扩展性/审计一致性）

**P1-1：DB events 与 artifacts events.jsonl 的“双写”缺少统一事务语义**

* 证据：worker 多处是 `insert_event` 后 `artifacts.append_event`，均是 best-effort；repair/maint 也各写各的。
* 风险：DB 成功但文件失败（或反之）→ 复盘证据不一致；对“互信审计”是硬伤。
* 终局修复：`EventSink`：同构结构 + 写入策略（至少保证：DB event_id 作为 artifacts 事件的引用；或者 artifacts 只做 DB 的投影缓存）。

**P1-2：配置读取散落（env 在 worker/executor/maint/repair 中各自读取），导致同一运行中行为不可预期**

* 证据：

  * worker/repair/gemini_web_mcp 都直接读大量 env。
  * gemini 的 rclone config path 有硬编码 fallback（`code/gemini_web_mcp.py:_rclone_config_path`）。
* 风险：部署/回滚时难以确认到底用了哪套参数；incident pack 也未必包含完整 config 快照。
* 终局修复：所有 env → `AppConfig`/`DriverConfig`，并在每个 job/incident manifest 固化“配置摘要 + schema 版本”。

**P1-3：provider-specific 逻辑泄漏到 worker 核心，扩展新 provider 成本高**

* 证据：worker 内直接做了 ChatGPT zip 展开、connector tool stub 检测、deep research completion guard、format_prompt 二次发送等（`code/worker.py`）。
* 风险：每加一个 provider 都要改 worker；worker 成为“上帝对象”。
* 终局修复：把 provider 特有行为迁入：

  * executors（调用策略）
  * guards/reconcile（可复用策略，但由 provider policy 参数化）
    worker 只做状态机与通用调度。

**P1-4：Ops 代码复用度低，maint_daemon 与 repair 都实现了相似能力（fingerprint、codex schema runner、action 风险分级）**

* 证据：maint_daemon/repair 都有 `_risk_allows/_parse_allow_actions`、都生成 codex prompt 与 schema 输出。
* 风险：两边演化不同步；护栏规则漂移。
* 终局修复：抽到 `chatgptrest/ops/` 库层，maint_daemon/repair 共用同一 ActionExecutor 与 CodexRunner。

---

### P2（长期技术债，影响稳定迭代速度）

**P2-1：工具命名与职责有历史包袱，容易误用**

* 例：`chatgpt_web_tab_stats` 实际返回 chatgpt/gemini/qwen 三者统计（见 `code/_tools_impl.py` 中实现），属于 driver-admin 工具但命名带 chatgpt_web。
* 风险：调用方误判工具语义；未来文档/监控混乱。
* 终局修复：保留旧名作为 alias，同时新增语义更正的 tool（或在 `driver.describe` 给出 canonical 名称），但外部 contract 不破坏。

**P2-2：启发式正则/文本归一化散落多处（deep research、infra error、connector stub），回归测试不够“白盒化”**

* 终局修复：集中到 taxonomy + golden tests（第4节给冻结项）。

---

## 3) 一次到位的迁移实施序列（阶段门禁、回滚点、灰度策略、失败保护）

下面是**单一路径**实施序列：每一步都“可合并、可回滚、可灰度”，但整体方向只有一个。

### Phase 0：冻结“互信约束”（先做，不改行为）

**目标**：把“不能破坏的东西”变成测试/快照/启动校验。
**交付物**：

1. REST v1 contract tests 扩充（你已有 `test_contract_v1.py`，补齐关键语义：见第4节）
2. MCP tools contract 升级：

   * 在现有 tool registry snapshot 基础上，新增 `mcp_tools_output_envelope_snapshot.json`（只抓关键字段，不追求全量）
   * driver 启动时生成 `schema_hash`；worker 启动时拉取并校验
3. 事件 taxonomy 冻结：`events.schema.json` + snapshot test
4. State/Artifacts manifest 冻结：`artifacts_manifest.schema.json` + 每个 job 写 `manifest.json`

**门禁**：

* 单测全绿（contract + snapshot + 新增 schema 校验）
* 生产开关默认不变（副作用动作仍默认关闭/受限）

**回滚点**：

* 纯新增测试/校验与 manifest 写入；回滚就是回退 commit，不涉及数据迁移

**灰度策略**：

* capabilities 校验先“告警模式”（记录 mismatch 但不阻断）跑 24h；再切到“阻断模式”（fail-closed）

**失败保护**：

* mismatch 时进入 `PAUSED`（按 provider）+ 返回 `cooldown/blocked`，绝不继续 send

---

### Phase 1：引入“共享 contracts + 单向依赖”骨架（不动逻辑）

**目标**：先把依赖方向固定住，防止拆分过程中产生环。
**交付物**：

* 新增 `chatgpt_contracts/` 并让两侧逐步引用（先从 taxonomy/paths 开始）
* 在 CI 加入“依赖方向检查”（简单 grep/AST 也行）：禁止 `chatgptrest` import `chatgpt_web_mcp`；禁止反向；只能共享 contracts
* driver/server 启动时把自身 build_info（版本、git sha、schema_hash）写到 artifacts/monitor 便于审计

**门禁**：

* 依赖检查通过
* 功能回归：contract tests + tool snapshot 通过

**回滚点**：

* 只是重排 import 与新增包；回滚安全

---

### Phase 2：把“副作用路径”收口到统一 Guard（仍保持行为兼容）

**目标**：把 send/重启/refresh 等副作用行为统一走一条“可审计、可预算、可 fail-closed”的路径。
**交付物**：

* `chatgptrest/core/side_effects.py`：`ActionGuard`（预算/冷却/熔断/drain-guard）
* `chatgpt_web_mcp/runtime/effects.py`：tool 级 `effect_level` 标注（read-only / ui-mutating / prompt-send / infra-restart）
* 把以下入口改为调用 guard，但保持原默认开关与行为：

  * worker format_prompt 二次发送（仍是 best-effort，但必须记录 guard decision）
  * repair.autofix actions 执行
  * maint_daemon infra healer / codex_sre_autofix actions 执行

**门禁**：

* 新增“副作用审计事件”必须出现且 schema 合法（例如 `action_attempted/action_skipped`）
* 12h soak（见第6节）中：副作用动作次数与基线一致或更低；无重启风暴

**回滚点**：

* Guard 引入通过 feature flag 控制：`CHATGPTREST_ACTION_GUARD_V1=1`
* 出问题可立刻关掉 guard 回到旧逻辑（但仍建议保留“记录模式”）

---

### Phase 3：把 worker 从“巨型流程”重构为“显式状态机 + 可测试组件”

**目标**：不再靠 meta/debug timeline 推断关键事实；把阶段职责拆清。
**交付物**：

1. `job_store` 增加稳定字段：

   * `prompt_sent_at` / `user_message_confirmed_at`（send-stage 原子写入）
   * `wait_started_at`（进入 wait-phase 写入）
2. worker 拆模块（见 1.2-C 的目录建议），并为每个 guard/reconcile 提供单测：

   * completion_guard（deep research ack、min_chars、export_missing_reply）
   * conversation_export reconcile（你已有 test_conversation_export_reconcile.py，扩展覆盖）
   * answer_get rehydrate（chunk 协议）
3. provider-specific 的东西迁出 worker：

   * ChatGPT zip 展开 → attachments 模块
   * connector stub 检测 → chatgpt provider guard
   * Gemini drive pipeline 已在 executor，保持但把 error taxonomy 对齐

**门禁**：

* “关键事实”不再从 `_debug_timeline` 推断（仅保留观测用 marker）
* 12h soak：duplicate prompt 事件为 0，conversation_busy 409 不上升，整体完成率不下降

**回滚点**：

* worker 新实现保留 `WORKER_V2=0/1` 选择（灰度：先 5% job kind，后全量）
* DB 新字段为可选（旧 worker 忽略），回滚无需回退 DB

---

### Phase 4：统一自愈闭环（只保留 maint_daemon 决策中心）

**目标**：避免自激振荡；把“修复决策”集中到 incident controller。
**交付物**：

* worker 侧 `_maybe_submit_worker_autofix` 永久降级为“只写事件信号”（默认不再直接 create repair.autofix job）
* maint_daemon 变成 `chatgptrest/ops/` 库驱动：

  * Observer → Correlator → FSM → EvidencePacker → ActionExecutor
* 引入 `actions_ledger`（SQLite 表或 artifacts/monitor 索引）：每个 action 有 fingerprint，保证“同一 incident 同一动作”不会反复执行

**门禁**：

* incident 级动作执行满足预算（比如 restart_* ≤ 1 次/30min/incident，且全局 ≤ N 次/小时）
* 12h soak：无 action oscillation（见第6节指标）

**回滚点**：

* 可以暂时关闭 `ENABLE_INFRA_HEALER` 与 `ENABLE_CODEX_SRE_AUTOFIX`，系统仍可运行（只是少自愈）

---

### Phase 5：最后清理与对外承诺固化（进入长期可维护态）

**目标**：移除临时兼容层中的业务逻辑，锁定“未来演进方式”。
**交付物**：

* compat 层只剩 alias + thin wrapper
* docs/contract_v1.md / issues_registry.yaml / runbook.md 更新为“与代码同源”（schema 驱动生成摘要）
* 新增 `ARCHITECTURE.md`：描述模块边界、依赖方向、升级流程、回滚流程

**门禁**：

* 所有 snapshot 更新都必须在 PR 中显式呈现 diff 并给出理由（审计要求）
* 12h soak 全绿（第6节）

---

## 4) 必须先冻结的可执行约束（强制先做）

这里列的是**“不冻结就不要继续拆”**的硬约束清单（全部可自动化）。

### 4.1 REST contract tests（v1）

在你现有 `test_contract_v1.py` 基础上，必须补齐以下可执行用例（覆盖三条链路）：

1. **幂等**

* 同 Idempotency-Key + 同 payload → 200 返回同 job_id
* 同 Idempotency-Key + 不同 payload（包括 file_paths 表达不同：绝对/相对）→ 409，`detail.error="idempotency_collision"`（contract 已写明）

2. **conversation single-flight**

* 同 conversation_url 同时 enqueue ask → 409 `conversation_busy`（除非 `allow_queue=true`）
* allow_queue=true 也不得出现并行 send（send worker 仍 enforce，一次只能一个 in_progress ask）

3. **send/wait phase 语义**

* send 阶段失败但已确认发送过用户消息 → 必须进入 wait-phase 重试，而不是重新 send（你现在靠 debug timeline/URL 推断，终局要靠 DB 字段）

4. **Gemini Drive fail-closed**（你 contract 明确）

* Drive URL 解析失败默认 `cooldown(reason_type=DriveUploadNotReady)`；永久错误 `error(error_type=DriveUploadFailed)`
* 仅当 `drive_name_fallback=true` 才允许走“文件名搜索”这种不可靠路径

5. **Qwen send throttle 默认 0、ChatGPT/Gemini 默认 61s**

* 三条链路 rate-limit key 独立（contract 已写明），不能互相影响

---

### 4.2 MCP tool schema snapshot + handshake

在现有 `test_mcp_tool_registry_snapshot.py` 上扩充：

1. **工具列表/参数 schema**（已有基础）
2. **关键输出 envelope schema**（新增，重点锁住）
   建议至少锁住以下工具的关键字段（不必全量 JSON schema，抓“必需字段集合 + 类型”即可）：

* `chatgpt_web_answer_get`: `ok/status/chunk/done/next_offset`
* `*_conversation_export`: `ok/status/export_path`（以及失败时 error_type/error/not_before/retry_after）
* `*_ask/*_wait`: `ok/status/conversation_url/error_type/error/retry_after/not_before/_debug_timeline.answer_id?...`（按你当前实现选择最小必要集合）
* `*_rate_limit_status`: `min_interval_seconds/last_sent_at_effective`
* `*_tab_stats`: `max_pages/in_use/limit_hits`

3. **capabilities handshake**（启动校验）

* driver 启动后提供 `schema_hash`（由 tool schemas + output envelope schema 计算）
* ChatgptREST worker 启动时拉取并校验：不一致直接 `PAUSED` + fail-closed（拒绝发送）

---

### 4.3 事件 taxonomy + schema（DB 与 artifacts 同构）

必须冻结：

* 事件类型集合（例如你已有：`auto_autofix_submitted`、`thought_guard_abnormal`、`answer_reconciled_from_conversation`、`conversation_export_forced` 等）
* 每个事件 payload 的字段 schema（允许“额外字段”，但核心字段必须存在）

并提供：

* `events.schema.json`
* `test_events_schema.py`：对 DB events 与 `artifacts/jobs/<id>/events.jsonl` 都跑 schema 校验
* `EventWriter`：唯一写事件入口，避免 worker/maint/repair 各写各的

---

### 4.4 State 路径与幂等语义冻结（防止“拆分后路径漂移”）

必须冻结：

* `ARTIFACTS_DIR/jobs/<job_id>/...` 的稳定文件名集合：

  * `request.json`（入参快照）
  * `run_meta.json`（执行元数据）
  * `answer.md|answer.txt`（最终答案）
  * `answer_raw.*`（format_prompt 前原始答案，若启用）
  * `conversation.json`（导出）
  * `events.jsonl`（同构事件流）
  * `manifest.json`（版本/哈希/引用汇总）
* driver state 根：

  * blocked_state 文件
  * rate_limit 文件
  * ui snapshot base dir
  * idempotency DB（必须包含 namespace/version）

幂等语义冻结：

* job 级 Idempotency-Key 的 hash 规则（包含 kind/input/params，不含 client）
* tool 级 idempotency_key 规则（例如 ChatGPT executor 的 `chatgptrest:{job_id}:{preset}`，以及 format_prompt 的 `exec_job_id=f"{job_id}:format"` 这一点必须当成 contract）

---

### 4.5 fail-closed 规则的可执行测试

必须冻结这些“安全底线”：

* **blocked/challenge**：不尝试绕过；最多采证据 + 暂停 + 提示人工（docs/maint_daemon.md 已写强约束）
* **Drive attach** 默认 fail-closed（Gemini）
* **任何 tool call 异常**：不能自动降级为“继续 send”（尤其是 send 阶段）
* **重启类动作**：必须 drain-guard（repair.py 已实现，maint_daemon 也应共用同一 guard）

---

## 5) auto repair / maintenance / issue-trigger / incident-trigger 的最终形态（避免自激振荡与误动作）

你的评审包里其实已经有“正确方向”的雏形：

* maint_daemon 设计草案明确了 FSM、事故包、护栏（docs/maint_daemon.md）
* repair.autofix 已有风险分级 + drain guard + allow_actions（code/repair.py）
  **终局建议：把它们合并成一个唯一闭环，并把“动作执行”严格约束为 fail-closed。**

### 5.1 终局组件（唯一决策中心：IncidentController）

**唯一决策中心：`IncidentController`（在 chatgptrest/ops/ 中）**
输入信号（只读）：

* DB events/jobs summary（maint_daemon 已实现 `_fetch_events/_jobs_summary`）
* blocked_state 文件（driver 写，maint 读）
* driver probes：`*_blocked_status/*_self_check/*_tab_stats/*_rate_limit_status`
* CDP probe：`/json/version`
* proxy probe：mihomo delay logs（你已经有 `mihomo_delay` 体系）

输出：

* Incident pack（manifest/summary/snapshots/actions.jsonl/codex/…）
* 结构化 action ledger（用于去重与预算）
* 可选：提交 `repair.check` job（仍是 job 化，便于统一审计）

### 5.2 触发机制：Issue-trigger vs Incident-trigger（单一路径）

**Issue-trigger（已知问题，来自 issues_registry.yaml）**

* 规则：当事件/错误命中 registry signals 时，进入“已知 playbook”
* 动作：优先只读采证据 → 低风险恢复（不发 prompt）
* 例：ISSUE-0005 TargetClosed/Crash：

  * 条件：infra error + CDP 异常
  * 动作：drain-guard → restart_chrome → self_check 复核 → 必要时 restart_driver
  * 冷却：同 incident 30 分钟最多一次重启；全局每小时最多 N 次

**Incident-trigger（未知/新型问题）**

* 默认：只采证据 + 降速/暂停（按 provider）+ 提示人工
* 只有在满足“重复出现/影响面扩大/证据齐全”时，才升级到 Codex SRE analyze（只读）
* Codex 输出动作建议后，仍需通过 allow_actions + max_risk + budgets + drain-guard 才能执行（即使 codex 说要做，也可能被 guard 拒绝）

### 5.3 防自激振荡（必须内建，不能靠“默认不开”）

把你现有的零散护栏收敛为四层“硬护栏”：

1. **去重（Dedup）**

* 以 `incident_signature + action_name + target_provider` 做 fingerprint
* 同 fingerprint 在冷却窗口内绝不重复执行（哪怕进程重启）

2. **预算（Budget）**

* per-incident：每类动作最大次数（如 restart_chrome ≤ 2/incident/24h）
* global：全局每小时/每天上限（防止系统性抖动时把自己打死）

3. **滞回（Hysteresis）**

* 必须“连续/累计失败达到阈值”才进入 RECOVERING 或执行动作
* 动作执行后必须等待观察窗（例如 2-5 分钟），且需要“复核信号变好”才允许下一步

4. **失败保护（Fail-closed）**

* 任一前置条件不满足（db 不可写、drain guard 失败、probe 不可达、schema mismatch）→ **跳过动作**，只写证据与告警
* 对 prompt-send：任何不确定性都不允许“试试看再发一次”

### 5.4 worker/repair/maint 的最终职责划分（消灭多入口）

* worker：只做 job 状态机；最多发出“需要修复”的事件信号（不直接修）
* repair.check：一次性诊断输出（可被 maint 触发，也可手工触发）
* repair.autofix：成为 ActionExecutor 的“计划生成器/执行器”之一，但所有动作仍受 IncidentController 的 ledger/预算统一约束
* maint_daemon：唯一的“触发与编排者”

---

## 6) merge-ready 与 prod-ready 的验收清单（含 12h soak 指标）

### 6.1 merge-ready（代码合并门槛）

必须全部满足：

1. **contract 不破坏**

* `docs/contract_v1.md` 对应的 contract tests 全绿
* 新增字段/事件/工具必须是“只增不改”，并有向后兼容

2. **MCP 工具快照与握手**

* tool registry snapshot 全绿
* output envelope snapshot 全绿
* driver/schema_hash 与 worker 校验逻辑具备，并默认“告警模式”可运行

3. **事件/错误 taxonomy 可执行**

* events schema 校验：DB events 与 artifacts events.jsonl 都通过
* error taxonomy：统一映射函数覆盖三条链路常见错误（infra/ui/blocked/quota/drive）

4. **副作用统一 guard 接入**

* format_prompt 二次发送走 guard
* restart/refresh/regenerate 走 guard
* drain-guard 对重启类动作强制生效

5. **依赖方向检查**

* `chatgptrest` 与 `chatgpt_web_mcp` 不得互相 import（只能共享 contracts）
* compat 层不得承载业务逻辑（只转发）

6. **最小回归集**

* chatgpt_web.ask（含附件/format_prompt/深度研究）
* gemini_web.ask（含 Drive 附件 + enable_import_code 分支）
* gemini_web.generate_image（含 Drive 参考图）
* qwen_web.ask（deep_thinking / deep_research 的状态与 cooldown 语义）
* repair.check / repair.autofix 的“无 prompt send”保证（至少通过“工具调用白名单”测试）

---

### 6.2 prod-ready（上线门槛）

除 merge-ready 外，再加：

1. **部署一致性与审计信息**

* API/worker/driver 的 build_info（git sha、schema_hash、config 摘要）会写入：

  * `artifacts/monitor/.../build_info.json`
  * 每个 job `manifest.json`（引用 build_info）

2. **灰度与回滚开关具备**

* `WORKER_V2` / `ACTION_GUARD` / `CAPABILITIES_ENFORCE` 等开关具备
* runbook 增补“如何一键回退到旧 worker/旧 driver”

3. **12h soak（硬指标）**

> soak 不是“跑着看”，而是“按指标判定是否允许进入下一阶段/是否允许全量”。

**12h soak 必须覆盖三条链路：**

* ChatGPT：至少包含

  * 普通 ask（preset=auto/pro_extended）
  * deep_research=true 的 job（允许 in_progress→wait 的长流程）
  * format_prompt 二次发送（验证节流与审计）
  * 附件（含 zip 展开路径）
* Gemini：至少包含

  * ask（含 Drive 附件上传与 fail-closed）
  * generate_image（含产物落盘与 answer markdown）
* Qwen：至少包含

  * deep_thinking
  * deep_research（可能触发 quota cooldown）

**关键指标（建议阈值，全部可从 DB events + jobs 表统计）：**

* **P0 指标（必须为 0）**

  1. `duplicate_prompt_guard` 相关的“真实重复发送”事件：0

     * 允许“guard skip”出现，但不允许出现“同一 job_id 再次 sent”
  2. 非预期的 `idempotency_collision`（同 key 同 payload 却冲突）：0
  3. “副作用动作在 send-phase 有 in_progress job 时执行”的事件：0（drain-guard 必须挡住）

* **可靠性指标（相对基线不得退化）**
  4) web ask 完成率（completed / 总数，按 provider 分开算）

  * 相比 Phase 0 基线：下降不得超过 **0.5 个百分点**

  5. `blocked` 与 `cooldown` 比例

     * 相比基线：上升不得超过 **0.5 个百分点**（或者采用你环境的历史均值 + 2σ）
  6. 平均 job 时长（p50/p90）

     * p90 不得恶化超过 **20%**

* **自愈稳定性指标（防振荡）**
  7) `restart_chrome/restart_driver` 总次数：

  * 12h 内 **≤ 2**（更理想是 0）
  * 且同一动作不允许在 30 分钟内重复（ledger 应保证）

  8. 每个 incident 的 action_attempts（actions.jsonl）

     * 单 incident 12h 内 ≤ 3（超过直接进入 PAUSED/MANUAL_REQUIRED）

* **资源与数据一致性**
  9) DB locked / db_write_panic 事件：0（你 worker 有 panic/autofix 机制，但 soak 要求“别走到那一步”）
  10) artifacts manifest 校验失败：0

---

## 7) 明确回答：现在应继续拆分还是先更长时间运行观察；量化判据

**结论（single best plan）：现在就继续拆分，但必须先把“观察”变成每一阶段的硬门禁，而不是无期限观望。**
理由很直接：你现在的体系里（从 worker/maint/repair/driver 的代码结构能看出）很多关键可靠性依赖“约定+启发式”，如果不趁现在把 contracts/taxonomy/guard/fsm 固化下来，后续任何维护都会把系统推回不可审计状态。

### 量化判据（什么时候“可以进入下一阶段拆分”，什么时候“必须停下先稳定运行”）

**允许继续进入 Phase 2/3（深入重构）的前置条件：Phase 0 基线 12h soak 达标**
满足以下全部条件即可推进：

1. P0 指标全为 0：

   * 无真实重复发送
   * 无非预期幂等冲突
   * 无绕过 drain-guard 的重启
2. 三条链路完成率相对基线下降 ≤ 0.5pp
3. restart 类动作 12h ≤ 2，且无 30min 内重复
4. DB/Artifacts 一致性错误为 0

**必须暂停拆分、先运行观察并修复的条件（触发任一条就暂停）：**

1. 12h 内出现任何“疑似重复发送”证据（哪怕最终被 guard 挡住但次数异常升高）
2. blocked/cooldown 比例相对基线上升 > 0.5pp 且持续 2h 以上
3. restart_chrome/driver 出现“连续两次以上”或出现 action oscillation（同一 incident 反复执行同一动作）
4. capabilities/schema mismatch 在生产出现（说明发布流程/版本管理不可靠）

**暂停时怎么做（仍按 single plan，不给多选项）：**

* 立即把系统切到 **fail-closed + PAUSED**（按 provider），只保留只读 probes 与事故包采集
* 用 incident pack + issues_registry + codex analyze 走一次闭环，先把根因稳定住，再恢复拆分节奏

---

如果你按上面这套“终局架构 + 冻结约束 + 单一决策中心 + 分阶段门禁”推进，最终会得到一个非常清晰的系统形态：

* **扩展性**：新增 provider/新 job kind，只需要加 `ProviderAdapter + Executor`，worker 不动。
* **可维护性**：每个模块职责单一，可测试；大多数改动不会触碰副作用路径。
* **可审计互信**：每次发送/重启/刷新都能在事件流与事故包里找到“谁决定的、为什么、护栏是否通过、证据是什么”。
* **行为兼容**：REST v1 不变、tool schema 受快照与 handshake 保护、三条链路全覆盖。