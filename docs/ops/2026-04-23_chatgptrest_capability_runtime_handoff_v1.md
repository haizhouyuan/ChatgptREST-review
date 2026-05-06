# 2026-04-23 ChatgptREST capability/runtime handoff v1

## 1. 这份交接文档的目的

本交接文档面向下一位接手的 agent，目标是把这轮围绕 **ChatGPT Pro 主链路修复、双模型评审保留、Gemini 生图验证、外审结论收口** 的工作一次性交代清楚，避免重复排查、重复试错、以及把“代码里还在”误判为“当前真正可用”。

这份文档覆盖：

1. 本轮任务背景与目标
2. 已完成的代码改动与提交
3. 已验证通过的真实能力样本
4. 外审（Pro / GeminiDT）结论摘要
5. 当前仍未完成或未重新 live 盖章的事项
6. 下一位 agent 的推荐执行顺序
7. 风险、注意事项、以及不要误碰的本地脏文件

---

## 2. 背景与用户真实诉求

本轮任务不是单点 bugfix，而是围绕 ChatgptREST 的能力治理与运行可靠性展开，用户的真实诉求先后明确为：

1. 修好 **问 Pro 拿不到答案** 的问题，做到真实闭环。
2. 不要头痛医头，要从：
   - 根因
   - 鲁棒性
   - 可维护性
   - 可观测性
   四个角度收口。
3. 对历史能力做一次严格盘点，区分：
   - 代码还在
   - 当前 contract 还在
   - 当前是否真的像 Pro 一样可用
4. 能力治理上，用户最终明确：
   - **双模型评审不要退役，要保留并确保好用**
   - **review 库代码评审还需要保留**
   - **ChatGPT 生图很强，需要作为新能力开发出来**
5. 要把问题抽象成更高层的 AI execution/control-plane 问题，让 Pro 和 GeminiDT 做外审，而不是只问“怎么修某个 selector”。
6. 最后用户要求出一份完整、详细、方便另一个 agent 接手的交接文档。

---

## 3. 本轮已完成的核心工作

### 3.1 ChatGPT Pro 主链路修复（真实闭环）

围绕 `chatgpt_web.ask` / public MCP automation 路径，已完成以下问题族修复：

#### A. wait-phase 真实进展被超时误杀
- 现象：答案已经增长，但仍被 `WaitNoProgressTimeout` 打回。
- 修复：在 wait timeout 判定前，显式记录：
  - `wait_partial_answer_progressed`
  - `wait_active_finalization_progressed`
- 关键提交：`b3386868`

#### B. Pro ask latency 预期不合理
- 现象：skill / agent 使用方容易把 Pro ask 当成同步立刻出结果。
- 修复：`skills-src/chatgptrest-call/SKILL.md` 明确 substantial Pro asks 是 async human-scale wait，通常 30 分钟级。
- 关键提交：`19fd20ab`

#### C. ChatGPT 上传链路对重附件不稳
- 现象：26 个附件 ask 触发 `Upload not confirmed in UI`。
- 修复：
  - 把超量文本型附件自动 bundling 成：
    - `CHATGPT_ATTACH_BUNDLE.md`
    - `CHATGPT_ATTACH_INDEX.md`
  - worker admission 前移，避免让 browser 去吞过多文件。
- 关键提交：`5f13d770` + `60c5b978`

#### D. generic upload input 被错误跳过
- 现象：误退回脆弱的 `+` 菜单，报 `Cannot find Upload file in the + menu.`
- 修复：在 `chatgpt_web_mcp/_tools_impl.py` 保留真实 generic input `upload-files`，只跳过 `upload-photos` / `upload-camera` / image-only accept。
- 关键提交：`60c5b978`

#### E. send timeout 误判成 same-session repair
- 现象：transport timeout 时，有些实际未发送的 job 被误判成“已发出但需同会话修复”。
- 修复：新增 `send_phase_evidence`：
  - `idempotency_sent`
  - `recovered_conversation_url`
  - `requested_conversation_url`
  - `safe_to_retry_send`
- 并把 base app URL 从“sent-thread evidence”里排除。
- 关键提交：`60c5b978`、`a3973201`

#### F. push-only receipt SLA 污染后台 wait budget
- 现象：调用方给 `max_wait_seconds=30` 只是想前台快返回 receipt，但后台 job 也被切成大量 30 秒 wait slice。
- 修复：public MCP 对 `push_only` / `push_plus_cache` 的后台 wait budget floor 到 1800 秒。
- 关键提交：`b68a268a`

#### G. wait 阶段只出短前言 / meta-commentary 时无主动恢复
- 现象：稳定 thread 上只有一句“我先看附件”之类的短前言或空 in-progress assistant，最后超时。
- 修复：增加 bounded same-thread `chatgpt_web_regenerate` 恢复梯度。
- 关键提交：`85ff8707`

#### H. compact-output 被过严 min_chars / quality guard 误伤
- 现象：明确要求简短结论或几点 bullet 的 ask 被错误判成不合格。
- 修复：
  - compact ask 默认 `min_chars` 降到 200
  - 明确 compact contract 的短多句回答可直接判成 `final`
- 关键提交：`dced8067`、`01f36c84`

---

### 3.2 双模型评审 retained capability 恢复为当前 MCP-native 能力

用户中途明确把“双模型评审可以退役”改成了：

> 双模型评审还是不退役了，继续使用，确保好用。

因此没有继续依赖 retired 的 `/v1/advisor/consult*`，而是直接在当前 MCP 层恢复 retained capability：

- `chatgptrest_consult`
- `chatgptrest_consult_result`

当前实现特征：
- 不依赖 retired REST advisor surface
- 直接 fan-out 真正的子 job（ChatGPT Pro / Gemini DeepThink）
- consultation state 落到：
  - `artifacts/consultations/<consultation_id>.json`
- 可通过 `chatgptrest_consult_result(...)` 聚合结果

关键提交：
- `eb9c777a` — `Retain dual-model consultation as an MCP-native capability`

---

### 3.3 Gemini 生图从“代码里有”推进到“真实可用”

本轮不是只做 contract 确认，而是真做了 live 修复与验证。

已完成修复：

#### A. prompt-entry keyboard fallback
- 解决 Gemini image prompt 输入框在某些页面态下 fill 失败的问题。
- 关键提交：`a51fc565`

#### B. rendered image screenshot fallback
- 当 `_gemini_fetch_bytes(...)` 失败时，从页面上已渲染的 `<img>` 元素直接截图输出 PNG。
- 关键提交：`ba4d849a`

最终成功样本：
- job：`d726d1b9d1754c16941963c917ab28ab`
- status：`completed`
- image artifact：
  - `artifacts/jobs/d726d1b9d1754c16941963c917ab28ab/images/20260422_224418_ai_16_9_4011.png`

---

### 3.4 外审包构建与有效外审回收

本轮为 Pro 与 GeminiDT 都构建并投递了**精简外审包**，不是泛泛空问。

外审包目录：
- `tmp/external_review_20260422_v1/`

关键文件：
- `2026-04-22_chatgptrest_external_review_brief_v1.md`
- `2026-04-22_chatgptrest_capability_decisions_v1.md`
- `2026-04-22_framework_reference_summary_v1.md`
- `2026-04-22_current_risk_matrix_v1.md`
- `2026-04-22_geminidt_compact_review_packet_v1.md`

有效外审结果：

#### Pro 外审
- job：`2ea1fc83b40948aba673b6d578981dd6`
- status：`completed`
- answer chars：`11573`

#### GeminiDT 外审
- 第一条 `b3441bb...` 串题到 STL / 散热支架，不可作为有效样本
- 重新提交紧凑、强约束版：
  - job：`be977b2bcbc4463fb635abf59dbcbb40`
  - status：`completed`
  - answer chars：`4090`

---

## 4. 已完成提交清单（按本轮任务相关性排序）

以下为这轮工作中最重要的提交，从旧到新：

1. `b3386868` — Keep wait-phase answer progress from timing out
2. `19fd20ab` — Set realistic latency expectations for Pro asks
3. `5f13d770` — Keep oversized Pro attachment sets within ChatGPT limits
4. `60c5b978` — Harden Pro send path against upload and timeout drift
5. `dced8067` — Relax Pro min-chars for compact automation asks
6. `b68a268a` — Decouple push wait budgets from foreground wait windows
7. `85ff8707` — Regenerate stalled Pro wait threads before timing out
8. `01f36c84` — Accept concise compact-output Pro answers as final
9. `eb9c777a` — Retain dual-model consultation as an MCP-native capability
10. `a3973201` — Keep base app URLs from masquerading as sent-thread evidence
11. `a51fc565` — Add keyboard fallback for Gemini image prompt entry
12. `ba4d849a` — Fall back to rendered screenshot capture for Gemini image bytes

---

## 5. 这次已经被真实验证为“当前可用”的能力

这里用严格口径：不是“代码里存在”，而是“已做 live 样本验证并 completed”。

### 5.1 已 live 盖章的能力

#### 1. ChatGPT Pro 外审 / 长答链路
- job：`2ea1fc83b40948aba673b6d578981dd6`
- `completed`
- `answer_chars = 11573`

#### 2. GeminiDT 外审 / 长答链路
- job：`be977b2bcbc4463fb635abf59dbcbb40`
- `completed`
- `answer_chars = 4090`

#### 3. 双模型评审（retained capability）
- consultation：`cons-d5fd9152d0584b60`
- child jobs：
  - ChatGPT Pro：`17fc7adb37864d5abcd9d599c234500c` → `completed`
  - Gemini DeepThink：`cd33b4ba9447459b86e9ed626492c466` → `completed`
- `chatgptrest_consult_result(...)` 可聚合返回

#### 4. Gemini 生图
- job：`d726d1b9d1754c16941963c917ab28ab`
- `completed`
- PNG artifact 已落盘

---

## 6. 仍在能力矩阵里，但这次没有单独重新 live 盖章的项目

### 6.1 review 库代码评审
- 当前仍应视作**主能力**，不是残留
- ChatGPT 路线：public repo URL / 附件包 review
- Gemini 路线：`github_repo + enable_import_code=true`
- 但这轮没有单独补一条新的 live repo-review 样本

### 6.2 ChatGPT Deep Research
- contract / executor 仍在
- 本轮未单独重新 live 验证

### 6.3 Gemini Deep Research
- contract / executor 仍在
- 本轮未单独重新 live 验证

---

## 7. 还未建设完成的新能力

### ChatGPT 生图
用户明确要求：

> chatgpt生图很强，我也需要开发出来

当前结论：
- 这不是“现成能力待确认”
- 而是**明确的新能力建设项**

建议最终形态：
- 独立 capability family：`chatgpt_image.generate`
- 独立 submit contract
- 独立 artifact plane
- 独立 result schema
- 独立 moderation / failure contract

---

## 8. 外审给出的终极架构建议（供下一个 agent 直接使用）

### 8.1 一句话结论

**不要再把问题理解成“继续修网页自动化脚本”，而要把 ChatgptREST 演化成 capability-oriented AI execution control plane。**

---

### 8.2 真正的 trust boundary

#### 不可信层
- Browser / Web UI / DOM / 页面按钮 / selector
- 第三方 provider 页面状态

#### 可信层
- ChatgptREST 自身的 capability registry
- preflight / admission
- state machine
- recovery ladder
- canonical result contract
- observability / operator tooling

外审和这次修复共同证明：
> UI 只能当作低信任执行外设，不能当作系统真相来源。

---

### 8.3 更优方法论方向

外审给出的方向，与用户提到的参考方向（`opencli` / `CLI-Anything`）是一致的：

1. **能力注册（capability registry）**
2. **契约优先（contract-first）**
3. **执行层解耦（lane / adapter）**
4. **统一结果面（final / provisional / partial / failed）**
5. **保留 advanced capability，但和 canonical public surface 明确区分**

当前本地参考仓路径（已核实）：
- `opencli`：`/vol1/1000/projects/jackwener/opencli`
- `CLI-Anything`：`/vol1/1000/projects/HKUDS/CLI-Anything`

注意：本轮只是把它们作为**方法论参考方向**纳入外审包，并没有做系统级源码对照分析。

---

### 8.4 外审对具体能力的定位建议

#### 双模型评审
- 应保留
- 但不应做默认主路径
- 更适合做：
  - high-value second opinion
  - conflict resolution
  - escalation lane

#### review 库代码评审
- 应保留为一等能力
- 不应退化成临时脚本或仅历史残留

#### ChatGPT 生图
- 值得做
- 但要作为独立 capability family，不要混进普通 `ask` 语义

---

## 9. 当前系统真实状态（截至交接时）

最新确认：
- `ops/health_probe.py --fix` → **PASS**
- `stuck_jobs = 0`
- `active_job_count = 0`
- systemd 关键服务全部 `active`

关键运行服务：
- `chatgptrest-api.service`
- `chatgptrest-mcp.service`
- `chatgptrest-driver.service`
- `chatgptrest-worker-send.service`
- `chatgptrest-worker-wait.service`

关键 artifact 仍存在：
- `artifacts/consultations/cons-d5fd9152d0584b60.json`
- `artifacts/jobs/d726d1b9d1754c16941963c917ab28ab/images/20260422_224418_ai_16_9_4011.png`

---

## 10. 下一位 agent 最推荐的执行顺序

### P0：优先做

#### 1. 给 review 库代码评审补 live 验证
目标：
- 跑一条真实 repo-review 样本
- 拿到 completed evidence
- 把它也提升到“像 Pro 一样已重新盖章可用”的状态

#### 2. 把双模型评审的 retained 能力文档化收口
当前代码已完成，但建议再明确文档口径：
- retained advanced capability
- 非 retired
- 非默认主路径
- 使用场景与边界清晰化

#### 3. 为 ChatGPT 生图写 PRD + contract 草案
建议产物：
- `docs/ops/2026-04-23_chatgpt_image_generate_capability_prd_v1.md`
- `docs/contracts/2026-04-23_chatgpt_image_generate_contract_v1.md`

---

### P1：随后做

#### 4. 建 capability registry
建议把散落在 route / executor / MCP tool / skill 里的能力，统一成 registry。

建议最少字段：
- capability_id
- family
- provider
- lane
- status
- maturity
- canonical entrypoint
- inputs
- preflight
- retry policy
- result schema
- observability contract

#### 5. 把 browser lane 正式降格为 adapter
需要文档和代码层都表达：
- UI 不是 control plane
- UI 状态不是系统真相
- browser 只是 provider-specific execution adapter

#### 6. 区分 canonical public surface 与 retained advanced capability
防止以后再混淆：
- 还能不能用
- 是不是 retired
- 是不是当前主入口

---

### P2：后续做

#### 7. 对 `opencli` / `CLI-Anything` 做方法论级对照分析
目标不是抄代码，而是总结：
- capability discovery
- tool/CLI abstraction
- executor decoupling
- result normalization
- extensibility

输出建议：
- `docs/ops/2026-04-23_chatgptrest_capability_architecture_benchmark_v1.md`

#### 8. 给 Deep Research 也补 live 盖章
分别补：
- ChatGPT DR
- Gemini DR

---

## 11. 本地脏文件提醒（不要误碰）

当前工作树里一直存在以下**非本轮任务产物**，不要误判为本轮残留：

- `.gitignore`
- `ops/chrome_stop.sh`
- `ops/systemd/chatgptrest.env.example`
- `ops/chrome_profile_state.py`
- `tmp/`

这些是用户本地已有脏改 / 未跟踪内容，不要擅自清理或混进后续提交。

---

## 12. 给下一位 agent 的一句话摘要

> 这轮已经把 ChatGPT Pro 主链路、双模型 retained consultation、Gemini 生图都修到并验证为真实可用；外审结论也明确支持把 ChatgptREST 往 capability-oriented control plane 演化。下一步最值得先做的是：**补 review 库代码评审 live 盖章**，以及**给 ChatGPT 生图正式立项（PRD + contract）**。

