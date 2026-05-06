# OpenMind / AIOS 落地评审报告（作者：codex）

日期：2026-03-01  
评审范围（以仓库现状为准）：  
- `openmind/` 当前代码（Kernel 为主）  
- `docs_model_routing_for_antigravity_2026-02-28.md` + `model_routing_profile.example.json`  
- `docs/llm-routing-6reports-2026-02-28/*`（路由报告归档）  
- `code review/*`（AIOS 需求/架构评审/红队摘要/跨仓背景材料）  

说明：你提到的 `docs/dev_log/INDEX.md`、`panoramic_analysis.md`、`implementation_plan.md`、`walkthrough.md` 在本仓库快照中未找到；本报告用以下“同义材料”替代引用：  
- “全景”：`code review/03_AIOS_REQUIREMENTS_BACKGROUND.md` 中的 `AIOS 需求全景 v5`  
- “方案/计划”：`code review/03_AIOS_REQUIREMENTS_BACKGROUND.md` 中的 `OpenClaw Phase 1 Implementation Plan`、以及 `docs_model_routing_for_antigravity_2026-02-28.md` 的最小实现建议与验证清单  
- “走查”：`code review/03_AIOS_REQUIREMENTS_BACKGROUND.md` 中的「4 个真实场景端到端走查」  

补充材料（跨仓旁证）：你随后提供的 `ChatgptREST` 侧《生产上线差距分析》（`/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-01_production_gap_analysis.md`）已在本仓库做成 digest：`exports/digests/2026-03-01_chatgptrest_production_gap_analysis_digest.md`；其列出的阻断项（双稿/脱敏/发布、Gate 评分、hybrid_search、EventBus/PolicyEngine 接入、checkpoint、quarantine）与本报告的 P0/P1 差距高度一致，可直接作为验收清单使用。  

---

## 1. 一句话结论

`openmind` 目前处于“Kernel 零件已落盘、但 Runtime/Connector/Apps 全缺失”的阶段，**不具备生产上线条件**；要上线，建议先以“写报告端到端自动化（含证据包、质量门禁、可回放）”作为唯一 P0 标杆链路，把契约、落盘、门禁、路由、长任务治理一次跑通，再扩展到 Research/Funnel/EvoMap。

---

## 2. 当前成果盘点（已落地/可复用）

### 2.1 OpenMind 代码现状（本仓库真实存在）

- Kernel 基础件（已实现，需加固）：  
  - `openmind/kernel/artifact_store.py`：内容寻址 ArtifactStore + provenance 记录  
  - `openmind/kernel/event_bus.py`：TraceEvent EventBus（SQLite 持久化 + in-proc pub/sub）  
  - `openmind/kernel/policy_engine.py`：质量门禁 PolicyEngine（结构/交付/成本/安全/claim-evidence）  
- 目录骨架已就位但基本为空：`openmind/advisor/`、`openmind/workflows/`、`openmind/kb/`、`openmind/evomap/`、`openmind/integrations/`  
- 依赖栈已在 `pyproject.toml` 声明（LangGraph/Qdrant/FastAPI 等），但尚未形成可运行入口（无 FastAPI app、无 CLI、无 E2E demo、无测试用例）。

### 2.2 路由与接入资料（可直接转为实现任务）

- 路由策略与接入规范：`docs_model_routing_for_antigravity_2026-02-28.md`  
- 路由配置样例：`model_routing_profile.example.json`（providers + routes + health_policy）  
- 六份路由报告归档：`docs/llm-routing-6reports-2026-02-28/INDEX.md`

### 2.3 需求/架构/红队结论（作为“初期目标与验收标准”基线）

- 需求全景与“零件齐全只差编排器”的诊断：`code review/03_AIOS_REQUIREMENTS_BACKGROUND.md`  
- 平台级架构评审请求/输出与强约束（契约、EvoMap、多模型机制必须工程化）：`code review/06_PRIOR_REVIEW_REQUESTS_AND_OUTPUTS.md`  
- 红队双模型共同高风险项与合并优先序：`code review/06_PRIOR_REVIEW_REQUESTS_AND_OUTPUTS.md`（redteam_comparison_summary）  

---

## 3. 生产上线差距：还差哪些工作（按“阻塞程度”排序）

> 这里的“上线”定义为：有稳定入口（API/CLI）+ 端到端可回放的最小业务链路 + 质量门禁与审计落地 + 失败可降级/可恢复。

### 3.1 P0 阻塞项（不做无法上线）

1) **缺少统一数据契约（Contract layer）**  
   - 现状：仅有 Artifact/TraceEvent/PolicyContext 这类“零件”，但没有统一的 TaskSpec/StepSpec/RunRecord/GateResult/Claim-EvidenceRef 等平台契约。  
   - 影响：无法做到“只靠契约驱动编排”“可回放审计”“跨 Connector 的一致失败语义”。  

2) **缺少 Runtime（可恢复执行器）**  
   - 现状：没有 Pipeline/Graph Runner；也没有长任务 checkpoint、挂起-重水合（rehydration）、并发/预算/熔断治理。  
   - 影响：一旦引入 Deep Research/辩论/外部发布，系统会立刻遇到红队所指出的“长时阻塞导致吞吐崩溃/状态丢失”问题。  

3) **缺少 Connector（外部系统接入层）**  
   - 现状：未实现 ModelRouter；未接入 ChatgptREST/CLI/OpenAI 兼容/Anthropic 兼容；未接入 KB pack/redact/publish 等。  
   - 影响：业务链路无法跑通；也无法做可测试的 mock/录制回放。  

4) **缺少 Apps/Workflows（至少 1 条标杆端到端链路）**  
   - 现状：README 里的 `Advisor Graph → Quick Ask/Deep Research/Funnel → KB ↔ EvoMap` 尚未落地；`openmind/workflows/funnel` 为空。  
   - 影响：无法形成“从输入到交付”的最小闭环，更谈不上“把手工方法论固化为系统能力”。  

5) **缺少测试与可验证性**  
   - 现状：`tests/` 为空（只有 `__init__.py`）；无 golden tests、无回放测试、无端到端验收脚本。  
   - 影响：任何“上线”都会变成不可控的手工验证，质量门禁也无法被工程化验收。  

### 3.2 P1 重要差距（做了才能“稳定上线”）

1) **ArtifactStore/SoT/门禁时序需要按红队结论加固**  
   - 红队共同结论：ArtifactStore 溯源语义、SoT 收敛、fail-closed 门禁时序、长任务治理、Block 替换稳定性、EvoMap plan-only 等均是根基风险。  
   - OpenMind 现状：只有“零件实现”，尚未形成“以事件+工件链路为 SoT”的运行事实闭合。  

2) **KB/记忆体系的统一桥接方案未落地**  
   - 文档指出存在三套独立记忆系统（HomeAgent/OpenClaw/planning KB），需要 staging→promote 与审计。  
   - OpenMind 现状：`openmind/kb/` 为空，无法承载“证据包→claim→回指→发布”的核心路径。  

3) **安全/脱敏/对外输出规范未工程化**  
   - 文档已有外发稿检查项与一致性校验思路；PolicyEngine 有雏形，但没有把门禁插入到真实副作用前（写盘/发布/外发）并形成审计记录。  

### 3.3 P2 扩展项（有了标杆链路后再做）

- 多场景扩展：Research pipeline、需求漏斗（Intake Funnel L0-L5）、投研、知识图谱等。  
- EvoMap 自进化闭环：信号→计划→审批→执行→隔离/回滚→晋级（必须先做到 plan-only + 审批 + 审计回流）。  

### 3.4 旁证：ChatgptREST 的“上线阻断项”可直接复用为验收清单

> 摘要见：`exports/digests/2026-03-01_chatgptrest_production_gap_analysis_digest.md`

- **报告链路闭环**：`report_graph` 必须补齐 “双稿（internal/external）→脱敏门控→发布”。  
- **Funnel 门禁工程化**：Gate rubric 评分不能是 stub；且需要异步暂停/恢复（对应长任务治理）。  
- **检索闭环**：`hybrid_search` 要有向量检索 + 融合（如 RRF）+ 降级 fallback。  
- **治理零件必须接入主链路**：EventBus emit、PolicyEngine gate、checkpoint 持久化缺一不可。  
- **KB 准入治理**：quarantine/stability 状态机是“可持续写回”的前置条件。  

---

## 4. “上线还差哪些工作要做”：详细待办清单（建议按 5 个阶段组织）

> 这里给的是“可落地的工程化清单”，每条都尽量对应到具体产物与验收方式，方便直接转成任务卡。

### Phase 0：先拍板的边界与验收（不拍板会导致后续反复返工）

1) MVP 只做 1 条链路还是多条？建议：**只做 A2 写报告端到端自动化**。  
2) “上线”的入口形态：FastAPI 服务 / CLI / 作为 Antigravity 的 importable SDK（可同时支持，但要确定主入口）。  
3) 单机还是分布式：建议 Phase 1 保持单进程 + SQLite WAL（先验收语义），Phase 2 再接队列/分布式锁。  
4) 存储 SoT：事件日志（append-only）+ 工件库（内容寻址）是否为唯一事实源（建议是）。  
5) 安全标签与受众枚举：`public/internal/confidential` 与 `internal/external/admin/...` 的口径统一（避免 PolicyGate 规则歧义）。  

### Phase 1：补齐 Contract + Kernel 加固（把“平台原语”做成可验收）

**1. Contracts（必须先做）**

- 新增 `openmind/contracts/`：  
  - `TaskSpec`：统一任务规格（intent、audience、risk、budgets、inputs、expected_outputs）  
  - `StepSpec` / `StepResult`：步骤规格与产物引用（含幂等键、重试语义、失败分类）  
  - `RunRecord`：一次运行的全链路记录（trace_id、状态机、checkpoint 指针）  
  - `ArtifactRef` / `EvidenceRef`：引用标准（内容寻址、类型、security_label）  
  - `Claim`：断言结构（claim_type、value、evidence_refs、confidence、verdict）  
  - `GateResult`：门禁输出（通过/阻塞原因/需人工复核/替换块建议）  
- 验收：给出最小 JSON 示例 + schema 校验测试（pydantic validation）。  

**2. ArtifactStore 加固（对齐红队的“溯源/一致性”风险）**

- 事务一致性：至少保证“写文件 + 写 DB 元数据 + 写 production 事件”具备可恢复语义（崩溃后能自愈/补账）。  
- 溯源语义：区分“artifact 不变元数据”和“production 事件可累积”；明确多次 production 的查询/审计接口。  
- 验收：断电/异常注入测试（模拟写到一半进程退出）+ 重启一致性检查。  

**3. PolicyEngine/QualityGate 加固**

- 明确 fail-closed 时序：**任何外部副作用（发布/外发/写入 KB promote）之前必须 Gate**。  
- 校验安全标签规则：当前 `PolicyEngine.check_delivery_label` 对 `confidential → external` 的处理需要确认是否符合预期（建议默认阻塞并要求人工审批）。  
- 验收：每条门禁规则都有单测；并且在端到端链路里能看到 GateResult 被落盘与可回放。  

**4. EventBus / SoT**

- 事件标准化：补齐事件类型枚举/命名规范、trace 传播、parent_event 语义。  
- 派生视图：最小实现“按 trace_id 回放 RunRecord”（即使先不做复杂查询，也要能还原执行过程）。  
- 验收：给定 trace_id 可以重放出“阶段、产物、门禁结果、错误与降级”的时间线。  

### Phase 2：Runtime Runner（可恢复执行、长任务治理、预算与并发）

1) Runtime Pipeline（9 阶段或等价实现，至少要可插拔与可测）  
   - ExecutionContextBuilder / MemoryProvider / PromptAssembler / ModelSelector / ToolRegistry / PlanAndCallRunner / ToolExecutor / ResponseStreamer / Telemetry  
2) Checkpoint + Rehydration  
   - 长任务（Deep Research、辩论）必须可挂起释放资源；恢复时从 checkpoint 继续，而非重跑/丢状态。  
3) 幂等与重试语义  
   - Step 级幂等键；可区分“可重试失败/不可重试失败/需人工介入”。  
4) 成本/延迟预算与熔断  
   - token/cost/time 的预算口径统一，并能落盘审计；provider 级熔断与冷却要工程化。  
5) 验收：  
   - 端到端跑一条任务可得到 RunRecord + ArtifactGraph + GateResult；  
   - 模拟 429/5xx/超时能够触发 fallback、熔断与恢复。  

### Phase 3：Connectors（把已有资产接进来，并且可测试/可回放）

**1. ModelRouter（按 `model_routing_profile.example.json` 落地）**

- 实现 `openmind/integrations/model_router.py`（或等价模块），支持：  
  - providers：OpenAI 兼容、Anthropic 兼容、CLI bridge、ChatgptREST  
  - routes：按 intent 选择 primary + fallback  
  - health_policy：连续失败冷却、超时、鉴权失败立即冷却  
  - 路由日志：`route_decision_log.jsonl` + EventBus 事件  
- 验收：按 `docs_model_routing_for_antigravity_2026-02-28.md` 的验证清单逐条通过。  

**2. KB Bridge（先桥接 planning/，再逐步内建）**

- 最小可行：封装 `kb_pack/kb_query/kb_redact` 为 subprocess connector，I/O 统一落成 Artifact。  
- 中期：实现 OpenMind 自己的 KB registry + FTS5 + Qdrant + hybrid search（与 docs/需求一致）。  
- 验收：给定项目/主题可以产出证据包（可回指到来源），并参与 claim-evidence 门禁。  

**3. 发布与对外输出 Connector**

- dingtalk_publish（或等价发布）必须在 Gate 后执行；发布清单与脱敏证据要落盘。  
- 验收：外发稿检查项（全中文/无内部痕迹/结论先行/篇幅）可自动跑，并形成 GateResult。  

### Phase 4：Apps/Workflows（只做 1 条标杆端到端链路）

建议只做：**写报告端到端自动化**（来自需求全景的 P0 链路）：

1) Purpose/Intent 识别：自动匹配目的矩阵 → 选模块组合  
2) 证据装载：自动 kb_pack → 生成证据包 Artifact  
3) 底稿生成：内部底稿（含材料索引、关键数字、假设）  
4) QG1：底稿完整性与结构门禁  
5) 外发稿生成：外发沟通稿（受众适配）  
6) QG2：外发稿门禁 + claim-evidence + 一致性校验  
7) 脱敏与发布：kb_redact + publish，并把发布记录写入 RunRecord/Meta 记忆  

验收：用“走查”里至少 1 个真实场景做 e2e 回放，保证每一步都有 artifacts、门禁点、失败降级与最终交付物。  

### Phase 5：工程化上线（CI/部署/观测/回滚）

1) FastAPI/CLI 主入口（选其一作为主入口）  
2) 配置与密钥管理（只读 env；支持 profile 文件；禁止明文 key 入仓）  
3) 观测与诊断：trace_id 贯穿日志；关键指标（latency/token/tool time/fallback 次数）可查询  
4) 测试与门禁：  
   - 单元测试（kernel/contracts/router）  
   - 集成测试（report pipeline）  
   - 回放测试（同 trace_id 重放一致）  
5) 发布策略：灰度/回滚/隔离（尤其是 EvoMap 相关能力，必须 plan-only 起步）  

---

## 5. 初期构想目标达成度对照（“哪些目标还没达成”）

| 初期目标（摘自文档/README） | 现状（以本仓库为准） | 未达成的核心差距 | 建议先补的最小落地 |
|---|---|---|---|
| Advisor Graph（理解意图→路由→执行→门禁） | `openmind/advisor/` 为空 | 无入口与执行框架 | 先做 1 条 report_pipeline + 最小 Advisor facade |
| Quick Ask / Deep Research / Funnel Graph | `openmind/workflows/` 基本为空 | 无 workflows 定义 | 先只落地 report_pipeline；Deep Research 作为 Connector 能力挂起 |
| KB（FTS5+jieba + Qdrant + fastembed + hybrid） | `openmind/kb/` 为空 | 无索引/检索/证据包 | 先桥接 planning KB 脚本，统一 I/O 为 Artifact |
| EvoMap（观察 TraceEvents → 计划 → 执行） | `openmind/evomap/` 为空 | 无 signal/plan/approval/审计闭环 | 先实现 signal 产出与 plan-only 待审队列（不自动执行） |
| TraceEvent EventBus（SQLite） | 已实现 `EventBus` | 尚未成为 SoT；缺派生视图 | 先实现 RunRecord 视图与 replay 验收 |
| ArtifactStore（内容寻址 + 溯源） | 已实现 `ArtifactStore` | 红队指出一致性/溯源语义风险仍需加固 | 做事务/补账/审计接口 + 崩溃恢复测试 |
| 质量门禁（fail-closed + claim-evidence） | 已有 `PolicyEngine` 雏形 | 未插入真实链路；规则口径需统一 | 在 report_pipeline 中强制 Gate 前置并落盘 GateResult |
| 多模型路由 + fallback + 熔断 | 仅有文档与 example profile | 未实现 ModelRouter/Provider | 先实现按 profile 路由 + health_policy + route log |
| “把手工标准变成自动执行管线” | 文档很强，代码未落地 | 缺编排器与可回放审计 | 以 report_pipeline 做标杆闭环，产出可回放 RunRecord |

---

## 6. 风险清单（从文档红队结论到本仓库落地的映射）

1) **溯源与一致性风险**：ArtifactStore 的“文件/DB/production 事件”一致性需要明确工程化策略，否则 SoT 无法闭合。  
2) **门禁时序风险**：若“先写盘/先发布再门禁”，就会出现无法撤回的泄露与错误交付。  
3) **长任务治理风险**：Deep Research/辩论/发布的时延与外部节流冲突若不做 checkpoint，会直接拖垮吞吐。  
4) **纯文本替换风险**：发布链路若依赖纯 Markdown patch，容易出现 drift；建议引入结构化 block（AST/Block JSON）再渲染发布态。  
5) **EvoMap 自动执行风险**：必须 plan-only + 审批 + 隔离/回滚；否则自进化闭环会把系统推入不可控状态。  

---

## 7. 结论与建议的下一步（最短路径）

结论：**不通过（未达到“可生产上线”的最低条件）**。  

建议你把接下来 2~4 周的目标收敛成一句话：  
> 在 `openmind` 内做出“写报告端到端自动化”的可运行闭环：有 TaskSpec/RunRecord/ArtifactStore/EventBus/PolicyGate/ModelRouter，并且可回放、可门禁、可降级。  

如果你确认这个方向，我可以下一步直接把 Phase 1~3 的最小实现拆成可落地的 repo-level 任务清单（按文件/模块/验收用例列出），并在 `Codereview/` 里补一份“可复制的验收脚本与演示用例”。
