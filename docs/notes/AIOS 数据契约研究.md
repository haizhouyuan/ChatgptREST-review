---
title: "AIOS 数据契约研究"
source: "https://chatgpt.com/c/69a12db9-5f84-83a6-b554-051ac75c416a"
author:
  - "[[ChatGPT]]"
published:
created: 2026-02-27
description: "ChatGPT is your AI chatbot for everyday use. Chat with the most advanced AI to explore ideas, solve problems, and learn faster."
tags:
  - "clippings"
---
aios\_deepresearch\_prompt\_planner\_pack\_20260227.zip

Zip Archive

请打开附件zip中的，严格按其要求输出；其余附件为上下文与规范。

---

---

### 2.1 一句话结论

- 为了把 AIOS 做成“可长期演进的个人级基础设施”而不是“脚本集合”，最该优先做 Deep Research 的方向是： **以事件溯源为核心的数据契约 + 以证据与门禁为核心的质量验证流水线 + 多模型可运行的交叉验证/仲裁机制 + EvoMap 治理式自进化桥接** ，因为这些决策一旦定错，后续所有应用（报告/调研/漏斗/治理）都会在不可追溯与不可控的返工中失血。

---

### 2.2 选题总览（排序）

> 说明：每个选题都聚焦“关键决策/关键不确定性”，且都能产出可直接落地的契约、流程、门禁与可替换块；并覆盖必须覆盖的五大域：报告端到端自动化、需求漏斗闭环、知识管理（记忆/KB）、多模型交叉验证/辩论机制、自进化闭环（EvoMap）。

#### P0（必须先研究，决定架构主干）

1. **题目：AIOS 核心数据契约 v1（TaskSpec / RunRecord / Artifact / Claim-Evidence / PolicyDecision）与事件溯源落盘格式**
	- 要解决的决策：AIOS 的“唯一事实来源”到底由哪些不可变事件与工件构成？各实体字段合同如何定义与演进？RunRecord/ArtifactGraph 用图还是表？错误语义如何统一（执行失败 vs 业务失败）？
	- 为什么必须 Deep Research：事件溯源、可追溯工件库、证据链与审计记录的“最佳实践/坑”高度依赖外部工程案例与标准（崩溃一致性、幂等、可回放、可审计、可演进 Schema）。
	- 不做的代价：后续报告/漏斗/多模型/自进化都只能靠“隐式约定”，导致证据无法回指、门禁无法自动化、数据迁移不可控，最终返工不可收敛。
	- 预期产出（可落地）： **Contract v1（字段表 + JSON Schema/伪 Schema + 事件类型表 + 版本演进策略）** 、可直接复制进 AIOS 的“可替换块”。
2. **题目：报告端到端自动化的规格驱动工作流（REPORT\_SPEC.yaml → 生成 → Pro 复审 → 脱敏 → 发布）与质量门禁链**
	- 要解决的决策：REPORT\_SPEC 作为单一事实来源如何在系统内落地？报告管线用 YAML pipeline 还是代码编排？质量门禁如何从“提示词要求”变成“系统强制步骤”（结构→DLP→claim→evidence→crosscheck→policy）？
	- 为什么必须 Deep Research：文档生成流水线、审稿闭环、脱敏/外发合规、证据门槛等需要对照行业实践（workflow 编排、DLP、审计、可回滚发布）。
	- 不做的代价：继续“手工喂标准”，迭代次数高，外发风险不可控；AIOS 无法证明自己是平台能力而不是一次性脚本。
	- 预期产出（可落地）： **report\_pipeline 参考流程图 + pipeline YAML 草案 + 质量门禁清单 + Pro 复审替换块合同 + 发布 manifest 合同** 。
3. **题目：需求漏斗闭环 v1（采集→清洗→提炼→分类→评估→收敛→派工→沉淀）到“项目卡”的可执行协议**
	- 要解决的决策：碎片输入如何标准化？收敛机制（价值/紧急/成本/风险/依赖）如何评分？脑暴/辩论如何插入而不失控？如何生成项目卡并与 PM 主链路（C0-C7）对齐？
	- 为什么必须 Deep Research：需求工程与 intake funnel 的对标范式很多（产品/研发/知识管理/Incident 管理），需要系统性对照后才能选“最适合个人级基础设施”的版本。
	- 不做的代价：入口继续堆碎片任务，无法形成“项目-里程碑-交付物-证据链”的闭环；PM/HR/KB 协作无法落地。
	- 预期产出（可落地）： **Funnel v1 规范（阶段输入输出+字段表）+ ProjectCard Schema + 收敛评分 Rubric + 派工包模板 + 端到端验收样例标准** 。
4. **题目：多模型交叉验证/辩论/仲裁机制（可运行的 Verification Pipeline）与成本/延迟控制**
	- 要解决的决策：多模型不是“多问几个模型”，而是可运行的流程：何时触发、角色怎么分、证据怎么回指、如何仲裁、如何 fail-closed、如何控成本与避免同源偏见？
	- 为什么必须 Deep Research：需要对照研究“debate/ensemble/judge/fact-check/RAG crosscheck”等方法的证据、适用边界与工程落地成本。
	- 不做的代价：质量门禁形同虚设，输出可信度无法提升；成本失控；复审只能靠人工。
	- 预期产出（可落地）： **Debate Loop 协议 + 仲裁决策矩阵 + 触发条件与预算策略 + 可直接复制的多角色提示词套件 + 质量提升验收指标** 。

#### P1（在主干确定后，决定系统可长期运行与可治理）

1. **题目：知识库（KB）与记忆层严格分离的架构与双视图 Schema v1（Agent 视图 / Human 视图）**
	- 要解决的决策：什么写入记忆、什么进入 KB？入库的 Claim-Evidence 结构是什么？双视图如何投影与脱敏？如何评估检索质量与证据可追溯？
	- 为什么必须 Deep Research：RAG/知识图谱/Provenance/数据治理实践丰富且差异大，必须对照后选定一套“可长期演进、可审计”的 schema 与流程。
	- 不做的代价：知识沉淀变成不可验证的“经验贴”，错误会被复用放大；对外材料风险上升。
	- 预期产出（可落地）： **KB/Memory schema v1 + 入库流水线（含历史会话提炼）+ 引用回指规范 + 脱敏策略与门禁规则 + 检索质量评估清单** 。
2. **题目：EvoMap 自进化闭环的桥接与治理（signals→plan→approval/budget→execute→audit→promote/rollback）**
	- 要解决的决策：AIOS EventLog/QualityGate 如何派生 signals？fingerprint 去重/风暴控制怎么做？预算与隔离/回滚门禁怎么设计？如何与 EvoMap 的类型与状态机对齐？
	- 为什么必须 Deep Research：自愈与自进化属于高风险自动化，需要对照 SRE、自动修复、策略升级、隔离回滚等成熟范式，避免“自动化造成更大事故”。
	- 不做的代价：系统无法从失败中进化；或者进化不可控、缺乏审批与隔离，反而引入安全/稳定性事故。
	- 预期产出（可落地）： **Signal taxonomy + 映射表 + Quarantine/Approval/Budget 策略 + Connector 合同 + 指标体系（hit/misfix/rollback 等）+ 验收门槛** 。
3. **题目：运行时调度与资源治理（并发/隔离/checkpoint/幂等/崩溃一致性）——SQLite WAL 事件库 + 文件工件库的一致性语义**
	- 要解决的决策：ArtifactStore 的“写文件+写 DB”原子性与幂等语义如何保证？PipelineRunner 的 checkpoint 与恢复策略怎么做？ResourceManager 的公平性/死锁边界如何验证？
	- 为什么必须 Deep Research：这类问题高度依赖成熟工程模式与已踩坑案例（exactly-once 近似、at-least-once + 幂等、两阶段提交替代、崩溃恢复、锁与队列公平性）。
	- 不做的代价：长期运行必出现“偶发坏账”（重复工件、丢事件、幽灵锁、内存泄漏），可追溯与可回放目标失效。
	- 预期产出（可落地）： **一致性语义说明书 + 失败模式矩阵 + checkpoint/恢复设计 + 幂等与副作用登记规范 + 压测/故障注入验收用例** 。

#### P2（增强项：让平台协作与接入策略长期可扩展）

1. **题目：组织与角色协议（PM/HR/Maint/KB）可执行化：从“规则”到“接口与状态机”**
	- 要解决的决策：PM 管项目、HR 管资源、KB 管沉淀、Maint 管阻断——如何变成系统可执行协议与最小字段合同？升级路径如何自动触发？配额与权限如何治理？
	- 为什么必须 Deep Research：要对照成熟组织治理/协作协议（RACI/SRE/Incident/项目治理），提炼成可落地的数据结构与流程，而不是口号。
	- 不做的代价：多 Agent 协作退化为“聊天分工”，无人对交付/证据负责；阻塞升级失效。
	- 预期产出（可落地）： **Role Contract 表 + 状态机/事件表 + 升级与配额策略 + 与 ProjectCard/TaskSpec 的字段映射 + 验收门禁** 。
2. **题目：模型载体/Provider 接入与归档策略（不改 ChatgptREST 前提下的路由、归档、风控）**
	- 要解决的决策：哪些调用必须走 ChatgptREST（长答落盘/幂等/队列/复审）？哪些可以走本地直连？如何做成本/可靠性/审计的路由策略？provider 资产台账字段如何定义？
	- 为什么必须 Deep Research：LLMOps、供应商接入、风控、成本治理都有成熟范式，需要对照后制定“可审计、可扩展”的策略，避免后期全盘重构。
	- 不做的代价：调用链路与归档不一致，审计与复盘失真；成本与可靠性不可控；多模型机制难以规模化。
	- 预期产出（可落地）： **载体选择矩阵 + 路由策略伪代码 + provider 资产台账 schema + 归档与审计字段合同 + 验收信号** 。

---

### 2.3 每个选题的 Deep Research Prompt（可直接复制运行）

> 说明：以下每段都是“独立可复制”的 Deep Research 提示词。你可以按顺序逐条投喂。  
> 共同硬约束： **输出中文；必须给可落地的可替换块；必须引用公开来源并可回指。**

---

#### 选题 1（P0）：AIOS 核心数据契约 v1 与事件溯源落盘格式 —— Deep Research Prompt

```markdown
Plain text1) 角色设定
你是一名“平台架构师 + 分布式系统可靠性工程师 + 数据契约设计专家”。你的任务不是写代码，而是给出可长期演进的契约与落盘语义，确保 AIOS 默认可追溯/可回放/可审计/可回滚。

2) 任务目标（必须回答的问题）
请基于公开资料与工程实践，回答并交付以下问题：
(1) 在“事件溯源（Event Sourcing）为唯一事实来源”的前提下，AIOS 的最小不可变事实集合应包含哪些事件类型？每类事件的字段合同如何定义？
(2) TaskSpec（任务规格）的字段合同 v1 应该如何设计，才能同时支持：报告自动化、需求漏斗、KB/记忆、多模型验证、自进化信号派生？哪些字段必须是一等字段，哪些可以作为扩展元数据？
(3) RunRecord（运行记录）应采用“事件流 + 视图派生”还是“强结构化 RunRecord 文档”还是“二者混合”？如何实现可回放与跨版本重算？
(4) Artifact（工件）与 Claim/Evidence（断言/证据）之间的关系用何种数据结构表达最稳健：图模型、关系表、或文档内引用？如何做可回指与可验证？
(5) PolicyDecision / GateResult / Error 语义如何统一，尤其是“执行失败 vs 业务失败”的区分？如何让下游能据此重试/隔离/升级？
(6) Schema 演进策略：版本号如何管理？字段新增/删除/语义变更如何兼容？历史事件如何迁移或通过投影兼容？
(7) 与内容寻址（sha256）ArtifactStore 的去重、不可变、溯源字段如何配合，形成“可审计工件图谱（ArtifactGraph）”？

3) 必须对照的方案/范式（至少 3 个，需比较优缺点与适用边界）
至少比较以下 4 类范式（可补充更多，但不得少于 3 类）：
- 范式A：纯事件溯源 + CQRS 读模型（只存事件，所有视图可重算）
- 范式B：事件溯源 + 快照（snapshot）/检查点（checkpoint）混合（事件 + 周期快照）
- 范式C：状态机/工作流引擎式状态存储（以状态表为主，事件为辅助审计）
- 范式D：引入通用可观测标准（如 trace/span/log 指标体系）与自定义事件并行

对每个范式给出：一致性语义、可回放性、实现复杂度、可演进性、成本、失败模式。

4) 证据与来源要求
- 必须引用公开来源并可回指（在结论处标注引用点）。
- 优先来源类型：系统设计论文/工程博客（需来自可信工程团队）/标准或规范/开源项目文档（事件溯源、内容寻址存储、审计日志、可观测）。
- 需要覆盖至少：事件溯源/CQRS、内容寻址存储（如 Git/IPFS 思路）、Provenance/审计日志、Schema 演进（如 JSON Schema/Protobuf/Avro 的工程策略）、SQLite WAL 与崩溃一致性相关经验。

5) 输出契约（必须按此结构输出）
你必须输出以下结构（标题不要改）：
A. 结论摘要（3-7条要点，带引用回指）
B. 决策对照表（范式A/B/C/D：优点/缺点/适用边界/与AIOS匹配度）
C. AIOS Contract v1（可替换块）
   - C1: AIOSEvent 事件类型表（event_type 列表 + 触发时机 + payload 字段）
   - C2: TaskSpec v1 字段表（字段名/类型/必填/语义/默认值/演进策略）
   - C3: StepSpec/StepResult v1（含 idempotency_key、business_success、error_category）
   - C4: Artifact v1（含 provenance、security_label、evidence_refs）
   - C5: Claim/EvidenceRef v1（claim_id、text、type、confidence、scope、evidence_refs）
   - C6: PolicyDecision/GateResult v1（allowed/decision/reason/conditions）
   - C7: Error 语义与错误码表（E_TRANSIENT/E_PERMANENT/E_CORRUPTION/E_POLICY）
D. 失败模式与边界条件（至少 12 条：如何发生、如何检测、如何缓解）
E. 落地步骤（按 3 个迭代阶段：先最小可用、再补齐、再治理优化）
F. 验收标准（可执行、可测量：至少 15 条验收信号/测试要点）
G. 风险与对策（至少 8 条）

6) 与本地材料的对齐点（只写文件名）
你必须显式对齐并引用这些材料中的约束与术语（不要引用路径）：
- AIOS_CONTEXT_DIGEST_R0_20260227.md
- AIOS_PLATFORM_INFRA_DESIGN_V0_20260227.md
- AIOS_DEVELOPMENT_PLAN_20260226.md
- AIOS_REQUIREMENTS_FULLVIEW_V5_20260227.md
并输出可直接用于替换落盘的“可替换块”位置建议，例如：
- “TaskSpec v1”替换块
- “RunRecord/ArtifactGraph v1”替换块
- “Error & PolicyDecision v1”替换块
- “事件类型表”替换块

7) Follow-up Questions（如信息不足，向我追问 5-10 个问题，按优先级）
请输出 10 个追问问题，优先级从高到低，聚焦：运行规模、数据保留、外发合规、并发与预算、存储位置与备份、隐私等级定义、对接系统契约等。
```

---

#### 选题 2（P0）：报告端到端自动化的规格驱动工作流与质量门禁链 —— Deep Research Prompt

```markdown
Plain text1) 角色设定
你是一名“工作流/编排架构师 + 文档工程负责人 + 信息安全与合规顾问”。目标是把‘写报告’固化为可自动执行的管线与门禁，而不是提示词手工艺。

2) 任务目标（必须回答的问题）
请研究并回答：
(1) “规格驱动（spec-first）”的报告生产线如何设计？REPORT_SPEC.yaml 作为单一事实来源时，哪些字段必须进入系统强制门禁？
(2) 报告端到端流程（目的识别→证据包→内部底稿→外发稿→复审替换块→脱敏→发布）在工程上如何拆成稳定步骤与可追溯工件？
(3) 质量门禁链（结构→DLP→claim抽取→evidence linking→crosscheck→policy）如何落地为自动化 verification pipeline？哪些门禁必须 fail-closed？
(4) Pro 复审闭环如何实现“替换块交付”契约？如何让模型输出能被系统自动应用/对齐/记录差异？
(5) 脱敏策略与对外发布如何通过 policy_engine 实现？如何避免外发稿暴露内部痕迹/路径/内部判断细节？
(6) 编排实现的选型：自研 PipelineRunner/YAML pipeline vs 采用通用工作流引擎（Temporal/Airflow/Dagster 等同类）vs LLM 编排框架（LangGraph 等同类）。结合个人级基础设施的约束，推荐哪条路线？
(7) 如何把“报告只是一个样例 App”与“平台内核不被绑死在报告上”工程化保证（接口边界、插件化、注册表、任务规格一致性）？

3) 必须对照的方案/范式（至少 3 个）
至少对照以下 3-5 类：
- 范式A：spec-first（类似 OpenAPI/配置驱动）+ 生成器 + 校验器
- 范式B：prompt-first（模板体系）+ 人工复审为主
- 范式C：通用工作流引擎（有持久化状态机、重试、可视化）承载管线
- 范式D：轻量自研 pipeline runner（事件溯源 + 工件库 + YAML 定义）
- 范式E：将验证流水线独立为 Verification Service（门禁即服务）

要求：给出对照表，明确为何适合/不适合 AIOS 约束（不改 ChatgptREST、需要可追溯/可回放/可审计、报告只是插件）。

4) 证据与来源要求
- 必须引用公开来源并可回指。
- 优先查：工作流引擎与文档生成流水线实践、审稿与人机协作（human-in-the-loop）最佳实践、DLP/脱敏/发布合规的工程方案、结构化输出与自动应用替换块的案例。
- 需要覆盖：文档生成系统的可追溯与版本治理、质量门禁自动化（lint/test/verification）、发布前合规检查。

5) 输出契约（必须按此结构输出）
A. 结论摘要（含推荐路线与理由，带引用回指）
B. 端到端流程分解图（步骤、输入、输出、工件、门禁）
C. 对照表（范式A/B/C/D/E 的优缺点与适用边界）
D. 可替换块（必须可直接落地）
   - D1: REPORT_SPEC.yaml 最小字段集（哪些字段必须、含校验规则）
   - D2: report_pipeline 步骤合同（StepSpec/StepResult 的关键字段）
   - D3: 质量门禁清单（结构/DLP/claim/evidence/crosscheck/policy）
   - D4: Pro 复审“替换块交付”合同（输入、输出结构、自动应用规则）
   - D5: 发布 manifest 合同（发布目标、脱敏记录、审计字段）
E. 失败模式与边界条件（至少 10 条）
F. 落地步骤（3 个迭代：最小可用→门禁补齐→多模型验证接入）
G. 验收标准（至少 15 条：端到端跑通、可回放、可审计、外发合规拦截、替换块可自动应用）

6) 与本地材料的对齐点（只写文件名）
必须对齐并引用：
- REPORT_SPEC_20260202.md
- PRO_REVIEW_LOOP_WORKFLOW_20260202.md
- REPORT_PURPOSE_MATRIX_20260208.md
- REPORT_TRIPLEKIT_PROMPTS_20260208.md
- AIOS_PLATFORM_INFRA_DESIGN_V0_20260227.md
- AIOS_CONTEXT_DIGEST_R0_20260227.md
并输出“可替换块”用于落盘到：
- report_pipeline.yaml（草案）
- QualityGate/Verification Pipeline（清单与规则）
- Pro 复审替换块协议

7) Follow-up Questions
输出 8-10 个追问问题，聚焦：报告类型覆盖范围、对外风险等级定义、证据门槛默认值、发布渠道约束、脱敏规则来源、是否允许 web 搜索与引用策略等。
```

---

#### 选题 3（P0）：需求漏斗闭环 v1 到项目卡的可执行协议 —— Deep Research Prompt

```markdown
Plain text1) 角色设定
你是一名“需求工程专家 + 产品运营/项目治理负责人 + 平台架构师”。你的交付目标是把‘碎片输入’变成‘可治理的项目卡’，并能与 PM/HR/KB 协作闭环。

2) 任务目标（必须回答的问题）
请研究并回答：
(1) 需求漏斗 v1 的阶段设计应如何定义，才能覆盖：采集→清洗→提炼→分类→评估→收敛→派工→沉淀，并且每一阶段都有明确输入/输出与可审计证据？
(2) 如何把“脑暴/辩论（多模型多角色）”嵌入漏斗，但不导致无限发散？什么时候必须收敛、收敛门槛如何定义？
(3) “项目卡（ProjectCard）”最小字段集应是什么？如何与项目治理状态流（draft→planned→active→blocked→review→closed）一致？
(4) 评估与优先级：价值/紧急/成本/风险/依赖/可逆性/证据充分性如何量化或半量化？给出可执行的 Rubric（评分规则 + 阈值 + 触发条件）。
(5) 派工包（dispatch package）如何结构化：owner/next_owner/blocker/evidence_path/eta 等字段如何落盘？如何保证“无证据路径不得宣告 covered”？
(6) 漏斗输出如何驱动 KB 入库与记忆写入：哪些产物必须沉淀为可检索知识？如何保证可回指来源与置信度？
(7) 如何让漏斗成为 App 而不是 Kernel：它依赖哪些平台原语（TaskSpec、EventLog、ArtifactStore、PolicyEngine）？

3) 必须对照的方案/范式（至少 3 个）
至少对照：
- 范式A：GTD/Inbox Triage（收集-澄清-组织-回顾-执行）映射到需求漏斗
- 范式B：产品 Backlog 管理（Epic/Story/Issue + Grooming + Sprint）映射到项目卡
- 范式C：Stage-Gate/投资决策门禁（证据门槛 + 决策门槛 + 风险门槛）
- 范式D：Incident/Problem Management（信号→分级→派单→复盘→知识沉淀）
要求：给出对照表，说明为何适合个人级 AIOS 的“长期演进 + 可审计 + 多 Agent 协作”。

4) 证据与来源要求
- 必须引用公开来源并可回指。
- 优先：需求工程/产品管理/项目治理方法论（经典与现代均可）、开源 issue/项目管理系统的字段设计、LLM 辅助 triage/分类/优先级的工程实践、证据门槛/门禁机制案例。

5) 输出契约（必须按此结构输出）
A. 结论摘要（含推荐漏斗 v1 形态）
B. 漏斗 v1 阶段定义（可替换块）
   - B1: 每阶段目的/输入/输出/门禁/失败语义
   - B2: 阶段事件与工件（哪些必须落盘为 Artifact）
C. ProjectCard Schema v1（可替换块：字段表 + 示例 JSON）
D. 收敛 Rubric（可替换块：评分表 + 阈值 + 决策分流：做/不做/延后/需研究）
E. 派工包模板（可替换块：owner/next_owner/blocker/evidence_path/eta/acceptance）
F. 与 KB/记忆接口（哪些入 KB，哪些入记忆，置信度与证据回指规则）
G. 失败模式与边界条件（至少 12 条：如信息噪声、重复输入、冲突需求、优先级漂移、无限辩论）
H. 落地步骤（3 个迭代：最小闭环→多模型辩论接入→与 PM/HR/KB 协议固化）
I. 验收标准（至少 12 条：2 条真实输入端到端跑通、可回放、可追溯、可派工、可入库）

6) 与本地材料的对齐点（只写文件名）
必须对齐并引用：
- REQ_FUNNEL_INPUT_V2_20260223.md
- PROJECT_GOVERNANCE_20260223.md
- PM_CHAIN_EXECUTION_V1_20260223.md
- AIOS_CONTEXT_DIGEST_R0_20260227.md
- AIOS_REQUIREMENTS_FULLVIEW_V5_20260227.md
并输出可直接落盘的“可替换块”：
- Funnel v1 规范块
- ProjectCard Schema v1 块
- 收敛 Rubric 块
- 派工包模板块

7) Follow-up Questions
输出 8-10 个追问问题，聚焦：输入渠道种类与规模、你希望的项目卡粒度、是否允许自动立项、你对“证据门槛”的偏好、与现有台账/工具的对接方式等。
```

---

#### 选题 4（P0）：多模型交叉验证/辩论/仲裁机制与成本控制 —— Deep Research Prompt

```markdown
Plain text1) 角色设定
你是一名“LLM 系统工程师 + 评测研究员 + 风控与成本治理负责人”。目标：设计一套可运行的多模型验证流水线（Verification Pipeline），能产出可审计的结论与证据回指，而不是口头建议。

2) 任务目标（必须回答的问题）
请研究并回答：
(1) 多模型交叉验证在 AIOS 的哪些环节必须使用（例如：关键结论、对外发布、写入 KB、自进化计划）？触发条件如何定义？
(2) Debate Loop（辩论机制）如何设计成可运行协议：角色（主张/反对/事实核查/裁判）如何分工？轮次如何限制？如何避免无限循环？
(3) 仲裁机制如何设计：投票、裁判模型、证据优先、规则优先、成本优先等策略如何组合？失败时如何 fail-closed？
(4) 如何用 Claim-Evidence 结构把“争议点”具体化：争议 claim 的拆分、证据链接、可信度评分如何做？
(5) 成本/延迟控制：预算字段如何进入决策（maxTokens/maxToolCalls/maxLatency 等）？何时降级为单模型 + 严格门禁？
(6) 如何避免同源偏见与模型互相“复读”：不同模型/不同提示/不同温度/不同证据源的设计要点是什么？
(7) 如何与事件溯源与 RunRecord 对齐：每轮辩论/核查必须落盘哪些事件与工件，才能复盘与审计？

3) 必须对照的方案/范式（至少 3 个）
至少对照以下 4 类（不得少于 3 类）：
- 范式A：Ensemble Voting（多模型独立回答 + 投票/加权）
- 范式B：Debate + Judge（对抗辩论 + 裁判模型裁决）
- 范式C：Self-consistency / Multi-sample（单模型多样本一致性 + 证据核查）
- 范式D：RAG Fact-check Pipeline（先检索证据再生成 + 生成后再核查）
要求：对照表包含准确性提升、成本、延迟、可审计性、实现复杂度、适用边界。

4) 证据与来源要求
- 必须引用公开来源并可回指。
- 优先：学术论文（debate/verification/ensembles）、工业实践（LLMOps、fact-check、safety gating）、开源框架文档（可用于实现多角色/多轮协议）、评测方法（如何度量提升）。
- 需要覆盖：错误模式（幻觉、引用漂移、过度自信）、仲裁失败处理、成本治理策略。

5) 输出契约（必须按此结构输出）
A. 结论摘要（推荐的 Verification Pipeline 形态与触发条件）
B. 对照表（范式A/B/C/D）
C. Verification Pipeline v1（可替换块）
   - C1: 触发条件与分流（何时多模型、何时单模型、何时必须人工审批）
   - C2: 角色与消息协议（字段合同：role、claim、evidence、verdict、confidence）
   - C3: 轮次与终止规则（防无限循环）
   - C4: 仲裁决策矩阵（规则优先/证据优先/成本优先的组合策略）
   - C5: 预算策略（maxTokens/maxToolCalls/maxLatency 的使用方式）
D. 失败模式与边界条件（至少 12 条：例如多模型一致但都错、证据不足、裁判偏置）
E. 与数据契约的对齐（RunRecord/Artifact/Claim-Evidence 需要新增哪些字段）
F. 落地步骤（3 个迭代：先关键发布与写入门禁→再扩展到调研/漏斗→再接入自进化）
G. 验收标准（至少 12 条：提升指标、成本上限、可审计性、复盘可回放）

6) 与本地材料的对齐点（只写文件名）
必须对齐并引用：
- AIOS_CONTEXT_DIGEST_R0_20260227.md
- AIOS_PLATFORM_INFRA_DESIGN_V0_20260227.md
- AIOS_REQUIREMENTS_FULLVIEW_V5_20260227.md
- AIOS_DEVELOPMENT_PLAN_20260226.md
并指出你的输出中哪些块可以直接替换落盘为：
- Verification Pipeline v1 规范块
- Debate prompts 套件块
- 仲裁矩阵与预算策略块

7) Follow-up Questions
输出 8-10 个追问问题，聚焦：你可用的模型集合与调用通道、预算上限偏好、哪些场景必须高证据门槛、对“人工审批”的可接受程度、输出可引用证据的最低要求等。
```

---

#### 选题 5（P1）：KB 与记忆分离 + 双视图 Schema v1 + 可追溯引用 —— Deep Research Prompt

```markdown
Plain text1) 角色设定
你是一名“知识管理架构师 + RAG/信息检索专家 + 数据治理/隐私合规顾问”。目标：建立可验证、可追溯、可演进的 KB/记忆体系，并支持 Agent 视图与 Human 视图双投影。

2) 任务目标（必须回答的问题）
请研究并回答：
(1) 记忆层（可写动态事实）与知识库（稳定可验证知识）如何严格分离？各自允许的写入类型、更新语义（覆盖/追加/过期）、以及审计要求是什么？
(2) KB 双视图（Agent 视图 / Human 视图）的核心差异应是什么：字段、脱敏、摘要粒度、引用回指方式、可见性策略？
(3) Claim-Evidence 的入库结构如何设计：claim 的类型/范围/置信度如何表达？evidence_refs 如何指向证据工件并可回指来源？
(4) 历史会话与产物的入库流水线如何设计：筛选→清洗→提炼→归档→索引→可追溯引用？哪些步骤必须人工审批？
(5) 检索质量如何评估：召回/精准/引用正确率/“可回指率”如何定义指标与抽样验收？
(6) 脱敏与对外边界如何在入库与输出时同时生效：policy_engine 与 kb_redact 的职责边界如何划分？
(7) 与“报告规格驱动”（REPORT_SPEC.yaml）如何对齐：sources.scope、evidence.level、context.distribution 等字段如何影响 KB/记忆读写策略？

3) 必须对照的方案/范式（至少 3 个）
至少对照以下 4 类（不得少于 3 类）：
- 范式A：向量检索（Vector DB）+ 元数据过滤 + 引用回指
- 范式B：知识图谱（Graph）+ 实体关系 + 溯源属性
- 范式C：混合检索（Hybrid：向量 + 关键词 + 图/元数据）
- 范式D：分层记忆（短期/长期/情景记忆）与语义知识库分离
要求：对照表包含实现复杂度、可追溯性、演进成本、适用边界、与个人级 AIOS 的匹配度。

4) 证据与来源要求
- 必须引用公开来源并可回指。
- 优先：RAG/检索评测论文、知识图谱与 provenance 标准/实践、工业知识库治理案例、脱敏/DLP 实践、开源检索系统文档。
- 必须覆盖：引用回指与可验证（provenance）、知识更新与版本治理、隐私与敏感信息处理。

5) 输出契约（必须按此结构输出）
A. 结论摘要（推荐的 KB/记忆架构与双视图策略）
B. 对照表（范式A/B/C/D）
C. Schema v1（可替换块）
   - C1: MemoryFact（记忆条目）字段表 + 更新语义
   - C2: KBClaim（知识断言）字段表（含 confidence、scope、evidence_refs）
   - C3: EvidenceRef 字段表（如何指向证据工件与来源）
   - C4: Dual View 投影规则（Agent View vs Human View）
D. 入库流水线 v1（可替换块：步骤/门禁/审批点/落盘工件）
E. 检索与引用评估方案（指标定义 + 抽样验收流程）
F. 脱敏与安全策略（policy_engine 与 redact 的分工 + fail-closed 场景）
G. 失败模式与边界条件（至少 12 条：例如引用漂移、过期知识、错误复用）
H. 落地步骤（3 个迭代：先 schema→再历史会话入库→再评估与治理自动化）
I. 验收标准（至少 12 条：可回指率、引用正确率、脱敏拦截率、审计完整性）

6) 与本地材料的对齐点（只写文件名）
必须对齐并引用：
- AIOS_CONTEXT_DIGEST_R0_20260227.md
- AIOS_REQUIREMENTS_FULLVIEW_V5_20260227.md
- REPORT_SPEC_20260202.md
- PRO_REVIEW_LOOP_WORKFLOW_20260202.md
- REQ_FUNNEL_INPUT_V2_20260223.md
并输出可直接落盘的“可替换块”：
- KB/Memory schema v1
- Dual View 投影规则
- 入库流水线 v1
- 检索质量验收清单

7) Follow-up Questions
输出 8-10 个追问问题，聚焦：你希望记忆写入的边界（哪些算“动态事实”）、KB 的主题分类/命名规范、是否允许自动写入或必须审批、对外分发等级、历史会话规模与清洗标准等。
```

---

#### 选题 6（P1）：EvoMap 自进化闭环桥接与治理 —— Deep Research Prompt

```markdown
Plain text1) 角色设定
你是一名“自适应系统/自愈架构师 + SRE 治理专家 + 风险控制负责人”。目标：让 AIOS 能从运行信号中产生可治理的进化计划，并通过审批/预算/隔离/回滚保障安全。

2) 任务目标（必须回答的问题）
请研究并回答：
(1) AIOS 的哪些事件与门禁结果应派生为 signals？signal 的 kind/severity/source/fingerprint 应如何定义，才能支持去重、风暴控制与长期统计？
(2) fingerprint 设计：如何保证“同类问题同 fingerprint”，同时避免误合并不同根因？给出可执行的 fingerprint 规则与示例。
(3) signals → evolution plan 的选择与生成策略：如何选 gene（改进领域）、如何选择 action（dispatch_task/send_followup/rollback/pause）？
(4) 审批与预算：哪些 plan 默认 requiresApproval？budget（maxRunSeconds/maxToolCalls/maxTokens）如何设置与动态调整？何时触发 budget_exceeded？
(5) quarantine 机制：连续失败如何隔离？隔离窗口与隔离时长如何设计？如何避免“误隔离导致系统瘫痪”？
(6) promote/rollback：capsule 晋级与回滚的门禁是什么？如何衡量 hit/misfix/rollback/circuit 等指标？
(7) 与 AIOS EventLog/RunRecord/PolicyDecision 的对齐：桥接接口如何定义，才能不重写 EvoMap 又能形成闭环？
(8) 自进化动作的风险分级：对“写文件/发布/写入 KB/执行命令”这类副作用，如何做默认保护（fail-closed + 审批）？

3) 必须对照的方案/范式（至少 3 个）
至少对照以下 4 类（不得少于 3 类）：
- 范式A：SRE Error Budget + Incident/Problem Management（以信号与预算治理改进）
- 范式B：Auto-remediation/Runbook Automation（自动修复与回滚）
- 范式C：GitOps/渐进式发布（promote/rollback 的治理式变更）
- 范式D：自主代理自我改进（需要强 guardrail 与审批）
要求：给出对照表，强调安全性、可控性、可审计性与误触发风险。

4) 证据与来源要求
- 必须引用公开来源并可回指。
- 优先：SRE/运维治理经典资料、自动修复/回滚机制工程案例、风险分级与审批制度实践、开源自愈系统/策略引擎文档。
- 必须覆盖：隔离/quarantine、预算守护、审批流程、改进效果度量（hit/misfix/rollback）。

5) 输出契约（必须按此结构输出）
A. 结论摘要（推荐的 EvoMap 桥接策略与治理原则）
B. 对照表（范式A/B/C/D）
C. Bridge Spec v1（可替换块）
   - C1: Signal taxonomy（kind/severity/source 的建议集合）
   - C2: fingerprint 规则（可执行规则 + 示例）
   - C3: AIOS→EvoMap 映射表（哪些事件/门禁 → 哪些 signal）
   - C4: Plan 模板（selector reasons、actions、riskLevel、requiresApproval、budget）
   - C5: Quarantine 策略（触发条件、窗口、解除条件）
   - C6: Promote/Rollback 门禁与指标（hit/misfix/rollback/circuit）
D. 失败模式与边界条件（至少 12 条：误触发、风暴、误隔离、自动化造成更大事故）
E. 落地步骤（3 个迭代：先派生 signals→再 plan-only→再执行与晋级回滚）
F. 验收标准（至少 12 条：信号去重效果、风暴控制、审批覆盖率、隔离有效性、指标可用性）

6) 与本地材料的对齐点（只写文件名）
必须对齐并引用：
- OPENCLAW_EVOMAP_TYPES_20260226.ts
- AIOS_PLATFORM_INFRA_DESIGN_V0_20260227.md
- AIOS_CONTEXT_DIGEST_R0_20260227.md
- PROJECT_GOVERNANCE_20260223.md
- PM_CHAIN_EXECUTION_V1_20260223.md
并输出可直接落盘的“可替换块”：
- Signal taxonomy + 映射表
- Quarantine/Approval/Budget 策略块
- Bridge 接口合同块

7) Follow-up Questions
输出 8-10 个追问问题，聚焦：你允许自动执行的动作边界、审批人的角色与响应时间预期、你对隔离误判的容忍度、预算默认值偏好、要优先改进的痛点类型等。
```

---

#### 选题 7（P1）：运行时调度与资源治理 + 崩溃一致性语义 —— Deep Research Prompt

```markdown
Plain text1) 角色设定
你是一名“并发与存储一致性专家 + 工作流运行时架构师 + 故障注入测试负责人”。目标：让 AIOS 能长期运行且可恢复，避免偶发坏账与隐式不一致。

2) 任务目标（必须回答的问题）
请研究并回答：
(1) 当 EventLog 使用 SQLite WAL、ArtifactStore 采用“文件写入 + DB 元数据”时，崩溃一致性如何定义？哪些操作必须原子？哪些允许最终一致？
(2) ArtifactStore 的“写文件 + 写 DB”边界如何设计：先写 DB 还是先写文件？如何通过临时文件 + rename、事务、幂等键减少坏账？如何做修复/回收？
(3) PipelineRunner 的 checkpoint 与恢复语义：长任务中断后如何恢复？如何保证不会重复产生副作用（发布/写入/派工）？
(4) 幂等与副作用登记：哪些步骤必须登记副作用并持久化？idempotency_key 的范围、生命周期与冲突策略是什么？
(5) ResourceManager 的并发治理：公平性（FIFO）与死锁边界如何证明/测试？如何设计资源层级与超时策略？
(6) 失败语义分类与重试策略：E_TRANSIENT/E_PERMANENT/E_CORRUPTION/E_POLICY 如何映射到重试/降级/隔离/升级？
(7) 如何建立“可观测的运行时健康度”：从事件派生哪些指标（队列、锁等待、失败率、重复率、缓存增长）？
(8) 如何用压测 + 故障注入验证：崩溃、断电、进程被杀、磁盘满、锁竞争、部分写入等场景？

3) 必须对照的方案/范式（至少 3 个）
至少对照：
- 范式A：at-least-once + 幂等（以幂等键与副作用登记保证“重复可接受”）
- 范式B：exactly-once 近似（事务性 outbox/两阶段提交/日志驱动）
- 范式C：把工件内容存 DB（BLOB） vs 文件系统内容寻址（content-addressed FS） vs 混合
- 范式D：通用工作流引擎的持久化状态机与重试语义（对照其做法）
要求：对照表包括一致性、复杂度、性能、可恢复性、实现成本。

4) 证据与来源要求
- 必须引用公开来源并可回指。
- 优先：SQLite WAL 与崩溃一致性经验、内容寻址存储的原子写入模式、幂等与副作用控制最佳实践、工作流引擎的 checkpoint/retry 语义、并发公平性与死锁预防资料。

5) 输出契约（必须按此结构输出）
A. 结论摘要（推荐的一致性与恢复语义）
B. 对照表（范式A/B/C/D）
C. 一致性语义说明书 v1（可替换块）
   - C1: 关键操作原子性定义（append event、store artifact、emit step result、publish）
   - C2: 事务边界与顺序（先后顺序 + 为什么）
   - C3: 幂等与副作用登记规范（字段表 + 示例）
   - C4: Checkpoint/恢复流程（状态机/事件序列）
D. 失败模式矩阵（至少 15 条：症状/根因/检测/修复/预防）
E. 压测与故障注入验收用例（至少 12 个可执行场景）
F. 运行时指标与告警建议（从 EventLog 派生的最小指标集）
G. 落地步骤（3 个迭代：先修语义→再加 checkpoint→再加故障注入与告警）
H. 验收标准（至少 12 条：无坏账、可恢复、无死锁、资源公平、缓存有界）

6) 与本地材料的对齐点（只写文件名）
必须对齐并引用：
- AIOS_CONTEXT_DIGEST_R0_20260227.md（已知工程风险点）
- AIOS_DEVELOPMENT_PLAN_20260226.md（WP1-WP5 的模块契约）
- AIOS_PLATFORM_INFRA_DESIGN_V0_20260227.md（事件溯源与工件库原则）
并输出可直接替换落盘的“可替换块”：
- 一致性语义 v1
- 幂等/副作用登记规范
- checkpoint/恢复流程
- 故障注入验收清单

7) Follow-up Questions
输出 8-10 个追问问题，聚焦：运行环境与磁盘/备份策略、是否需要跨进程/跨机器、哪些步骤有不可逆副作用、你可接受的恢复点目标（RPO/RTO 类似概念）、并发规模与资源种类等。
```

---

#### 选题 8（P2）：组织与角色协议可执行化（PM/HR/Maint/KB）—— Deep Research Prompt

---

#### 选题 9（P2）：模型载体/Provider 接入与归档策略（不改 ChatgptREST）—— Deep Research Prompt

```markdown
Plain text1) 角色设定
你是一名“LLMOps/平台接入架构师 + 成本治理负责人 + 审计合规顾问”。目标：在不修改 ChatgptREST 的前提下，设计可审计、可扩展、可控成本的模型调用路由与归档策略。

2) 任务目标（必须回答的问题）
请研究并回答：
(1) 在 AIOS 中，哪些场景必须统一走 ChatgptREST（长答落盘/幂等/队列/复审），哪些可以直连（若允许）？给出决策矩阵。
(2) 多模型机制如何在“归档一致性”上成立：不同载体/不同模型的输入输出如何统一成可审计 RunRecord 与 Artifact？
(3) provider/会员/鉴权资产台账应有哪些字段：到期、权限、额度、用途、风险等级、可用通道、成本等？如何避免凭据散落？
(4) 路由策略如何编码：基于任务风险等级、预算、延迟要求、证据门槛、是否需要 web 搜索等字段的分流伪代码。
(5) 失败与降级：当某通道不稳定或额度不足时，如何降级而不掩盖问题？如何记录为 signals 供 EvoMap 演进？
(6) 成本治理：如何在 TaskSpec 的 budget 与 policy_engine 中落地“最大成本/最大调用次数/最大 tokens”的硬约束？

3) 必须对照的方案/范式（至少 3 个）
至少对照：
- 范式A：All-in Gateway（所有模型调用统一经一个服务归档与治理）
- 范式B：Hybrid（关键链路经 Gateway，其余本地直连，统一落盘）
- 范式C：Per-capability Provider（按能力块选择 provider，统一路由策略）
- 范式D：按风险分级（高风险强治理/强审批，低风险轻治理）
要求：对照表包含审计一致性、实现复杂度、可靠性、成本、扩展性。

4) 证据与来源要求
- 必须引用公开来源并可回指。
- 优先：LLMOps/成本治理/供应商接入实践、审计与归档策略案例、可靠性与降级策略资料。

5) 输出契约（必须按此结构输出）
A. 结论摘要（推荐的接入与路由策略）
B. 对照表（范式A/B/C/D）
C. 可替换块
   - C1: 载体选择矩阵（场景→推荐载体→理由→风险）
   - C2: Provider 资产台账 Schema v1（字段表 + 示例）
   - C3: 路由策略伪代码（基于 risk_level、budget、evidence.level、sources.scope 等）
   - C4: 归档字段合同（如何映射到 RunRecord/Artifact）
D. 失败模式与降级策略（至少 10 条）
E. 落地步骤（2-3 个迭代）
F. 验收标准（至少 10 条：归档一致性、成本上限、失败可观测、降级不掩盖问题）

6) 与本地材料的对齐点（只写文件名）
必须对齐并引用：
- AIOS_CONTEXT_DIGEST_R0_20260227.md（不改 ChatgptREST 约束）
- REQ_FUNNEL_INPUT_V2_20260223.md（模型/载体选择矩阵与资产台账需求）
- AIOS_PLATFORM_INFRA_DESIGN_V0_20260227.md（Web 通道不做关键路径依赖等原则）
- AIOS_DEVELOPMENT_PLAN_20260226.md（budget/policy 字段与错误语义）
并输出可直接落盘的“可替换块”：
- 载体选择矩阵
- Provider 台账 schema
- 路由策略伪代码与门禁规则

7) Follow-up Questions
输出 6-10 个追问问题，聚焦：你当前可用的载体与模型集合、你对归档的强制程度、成本上限与优先级、哪些任务必须 web 搜索、对凭据治理的现状等。
```

---

### 2.4 研究执行顺序与里程碑

> 原则：先锁“平台契约与可审计运行记录”，再锁“最关键业务样例（报告）+ 验证机制（多模型）+ 漏斗闭环”，随后补齐“知识治理/自进化/运行时可靠性”，最后再做“组织协议与接入策略”。

#### Iteration 1（P0：定主干，决定能不能成为平台）

1. 先跑 **选题1（数据契约 v1）**
	- 验收信号：
		- 输出包含：事件类型表 + TaskSpec/Artifact/Claim/PolicyDecision/Error 的字段合同（可直接复制）。
		- 给出明确的 schema 演进策略与至少 15 条可执行验收标准。
2. 并行/随后跑 **选题2（报告端到端自动化）**
	- 验收信号：
		- 产出 report\_pipeline 的步骤合同与门禁链清单（结构/DLP/claim/evidence/crosscheck/policy）。
		- 明确 Pro 复审“替换块”输入输出合同与自动应用规则。
3. 并行/随后跑 **选题4（多模型验证/辩论/仲裁）**
	- 验收信号：
		- 产出 Verification Pipeline v1 规范（触发条件、角色协议、仲裁矩阵、预算策略、终止规则）。
		- 产出可直接复制的多角色提示词套件（至少 4 角色）。
4. 最后跑 **选题3（需求漏斗闭环到项目卡）**
	- 验收信号：
		- 产出 Funnel v1 阶段定义 + ProjectCard Schema + 收敛 Rubric + 派工包模板。
		- 明确与 PM 主链路（C0-C7）字段映射与门禁点。

#### Iteration 2（P1：可长期运行与可治理）

1. 先跑 **选题7（运行时可靠性/一致性/调度治理）**
	- 验收信号：
		- 产出“一致性语义说明书 v1 + 失败模式矩阵 + 故障注入清单”，可直接转为测试用例。
2. 再跑 **选题5（KB/记忆分离与双视图 Schema）**
	- 验收信号：
		- 产出 KB/Memory schema v1 + 入库流水线 v1 + 检索质量验收指标与抽样流程。
3. 再跑 **选题6（EvoMap 桥接与治理）**
	- 验收信号：
		- 产出 signal taxonomy + 映射表 + quarantine/approval/budget 策略 + 指标体系（hit/misfix/rollback 等）。

#### Iteration 3（P2：规模化协作与接入策略）

1. 跑 **选题8（组织与角色协议可执行化）**
	- 验收信号：
		- 产出 Role Protocol v1（字段合同、状态机、升级策略、指标定义），可直接落盘为治理规范。
2. 跑 **选题9（模型载体/provider 接入与归档策略）**
	- 验收信号：
		- 产出载体选择矩阵 + provider 台账 schema + 路由策略伪代码 + 失败降级策略，且与 TaskSpec budget/policy 对齐。

---

### 2.5 你认为材料包仍缺什么（仅列缺口，不要脑补）

> 说明：以下是“会影响研究结论准确性或可落地性”的信息缺口；每条都标注影响选题与建议补齐方式（台账/配置/测量/样例）。

1. **缺口：ChatgptREST 的调用契约细节（接口字段、归档字段、错误语义、幂等键规则）未在材料包给出**
	- 影响选题：选题2、选题4、选题9、选题1
	- 建议补齐：补一份“ChatgptREST 对接契约摘要（字段/状态/错误/幂等）”或导出一份最小调用示例与归档产物样例。
2. **缺口：kb\_pack / kb\_query / kb\_redact 的输入输出合同与失败语义（success vs business\_success）未给出**
	- 影响选题：选题2、选题5、选题4、选题7
	- 建议补齐：补“KB 工具链接口台账（参数、输出结构、错误码、超时/重试策略、落盘工件结构）”。
3. **缺口：安全分级（public/internal/confidential）的精确定义、默认策略与对外红线未明确**
	- 影响选题：选题1、选题2、选题5、选题6、选题9
	- 建议补齐：补一份“信息分级与外发策略基线（分级定义、默认门禁、例外审批规则、脱敏规则来源）”。
4. **缺口：真实运行规模与资源预算（并发任务数、平均任务时长、可接受延迟、月度成本上限）未提供**
	- 影响选题：选题7、选题4、选题9、选题1
	- 建议补齐：补一次“现网测量/期望预算台账”（哪怕是粗粒度区间），并明确哪些任务必须强实时、哪些可离线。
5. **缺口：AIOS 持久化边界与数据目录策略的最终决策尚未落地**
	- 影响选题：选题1、选题7、选题5
	- 建议补齐：补一份“数据落盘策略决策记录（数据目录、备份、迁移、加密、保留周期）”。
6. **缺口：对外发布渠道（钉钉/文档系统）的发布合同与审计字段要求未明确**
	- 影响选题：选题2、选题1、选题5
	- 建议补齐：补“发布目标与审计字段清单（发布对象、权限模型、回滚方式、发布 manifest 必填字段）”。
7. **缺口：报告类型覆盖的优先级与默认 REPORT\_SPEC 模板集合（哪些场景必须覆盖、哪些后置）未给出**
	- 影响选题：选题2、选题4、选题5
	- 建议补齐：补“报告场景覆盖矩阵（按目的矩阵映射）+ 每类的默认 evidence.level 与 sources.scope”。
8. **缺口：需求漏斗输入渠道的具体类型与样例（语音/截图/链接/历史会话等）的真实样本未提供**
	- 影响选题：选题3、选题5、选题4
	- 建议补齐：补至少 10 条“真实输入样例（脱敏后）”，并标注你期望的输出（项目卡/入库/派工）。
9. **缺口：项目卡与台账的现有存储形态（文件、表格、数据库）与更新流程未说明**
	- 影响选题：选题3、选题8、选题1
	- 建议补齐：补“当前项目台账样例 + 更新规则 + 证据路径约定”。
10. **缺口：多模型可用清单（哪些模型、哪些通道、哪些限制）与“必须多模型”的风险场景定义不完整**
- 影响选题：选题4、选题9
- 建议补齐：补“模型/载体资产台账（可用性、额度、限制、适用场景）”与“高风险场景列表”。
1. **缺口：EvoMap 在你的实际使用中，计划生成（selector/gene）与动作执行（dispatch/rollback 等）的真实样例与评估口径未提供**
- 影响选题：选题6、选题8
- 建议补齐：补 3-5 个 EvoMap 的历史 plan/run/capsule 样例（可脱敏），以及你对“命中/误修/回滚”的判定口径。
1. **缺口：PolicyEngine 的规则来源与可配置性要求（硬编码 vs 配置、规则版本治理）未明确**
- 影响选题：选题1、选题2、选题5、选题9
- 建议补齐：补“策略规则台账（规则列表、优先级、例外、审批、版本号）”或一份最小配置草案。
1. **缺口：质量门禁的“最低可接受证据门槛”与“何时允许无证据输出”的政策未明确**
- 影响选题：选题2、选题4、选题5、选题3
- 建议补齐：补一份“证据门槛政策（high/medium/low 的定义与拦截策略）”，并给 2-3 个示例。
1. **缺口：ResourceManager 要治理的资源集合与稀缺资源定义（browser、各模型通道等）缺少枚举与优先级**
- 影响选题：选题7、选题4、选题9
- 建议补齐：补“资源清单（资源名、并发上限、超时、优先级、降级策略）”与一次并发冲突复现记录。
1. **缺口：对“写入类副作用”（写 KB、发布、执行命令、修改项目台账）的默认审批策略与授权边界未冻结**
- 影响选题：选题2、选题5、选题6、选题7、选题8
- 建议补齐：补“副作用白名单/黑名单 + 审批流程（谁批、何时批、需要哪些证据）”的最小决策记录。