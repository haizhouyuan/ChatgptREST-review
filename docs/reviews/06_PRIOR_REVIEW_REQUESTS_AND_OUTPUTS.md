# Prior Review Requests And Outputs

Source repo: `/vol1/1000/projects/planning/aios`
Generated: 2026-02-28

Goal: Preserve review intent, evaluation criteria, and previous model outputs so new research can continue from prior context.

---
## Source: REQUEST_aios_platform_arch_review_R1_20260227.md
Path: /vol1/1000/projects/planning/aios/docs/specs/REQUEST_aios_platform_arch_review_R1_20260227.md

---
title: REQUEST - AIOS 平台级基础设施全盘架构评审 R1
date: 2026-02-27
audience: ChatGPT Pro Extended / Gemini Deep Think
language: zh
---

# REQUEST：AIOS 平台级基础设施全盘架构评审（R1）

你将收到一个最小材料包（若干文件）。请基于这些文件内容，给出 **AIOS 全盘架构设计 + 业务流程 + 实现逻辑** 的可执行方案。

材料包文件清单（请只按文件名引用）：
- `AIOS_REQUIREMENTS_FULLVIEW_V5_20260227.md`
- `AIOS_PLATFORM_INFRA_DESIGN_V0_20260227.md`
- `REPORT_SPEC_20260202.md`
- `PRO_REVIEW_LOOP_WORKFLOW_20260202.md`
- `REPORT_PURPOSE_MATRIX_20260208.md`
- `REPORT_TRIPLEKIT_PROMPTS_20260208.md`
- `OPENCLAW_EVOMAP_TYPES_20260226.ts`

## 0. 背景与目标（必须按此理解）

我要做的是“个人级基础设施底座”（AIOS），目标不是只为某一个应用服务，而是能承载未来未知类别的各类应用，并且在运行中能自进化。

同时，我已经有很多成熟资产散落在多个仓库：planning/research/homeagent/storyplay/openclaw 等。AIOS 需要把这些资产“固化成可自动执行的管线与门禁”，把高标准的方法论从手工艺变成系统能力。

## 1. 强约束（必须遵守）

1) 全中文表达（可出现少量英文代码/字段名，但首次出现需给中文解释）。  
2) **只按文件名引用**：不要输出任何本地路径、目录名、盘符、URL（除非材料里已出现且必须引用）。  
3) 不要“重写所有内容”，要输出可落地的“模块边界 + 数据契约 + 里程碑 + 验收标准 + 风险对策”。  
4) 必须把 EvoMap 纳入整体设计（自进化闭环是硬需求）。  
5) 需要多模型/交叉验证/辩论机制时，要把它设计成可运行的流程，而不是一句建议。  

## 2. 你需要交付的内容（输出结构硬要求）

请按以下结构输出（不要改标题层级，方便我做替换块落地与后续追问）：

### 2.1 一句话结论
- 用 1-2 句话说清：AIOS 的平台级架构应该如何定、先做什么、为什么。

### 2.2 需求全景再拆解（用你自己的话重述，但不新增需求）
- 把需求分成“平台能力”与“应用能力”两层。
- 标出你认为的 P0/P1/P2（带理由）。

### 2.3 平台分层与模块边界（必须给清单）
- Kernel / Runtime / Connector / Apps 各自职责与“禁止做什么”。
- 我需要哪些核心模块（例如：TaskSpec、RunRecord、ArtifactGraph、PolicyGate、Memory、Router、Scheduler 等），每个模块：
  - 输入输出（字段级）
  - 依赖（哪些模块/外部系统）
  - 失败语义（失败如何落盘、是否重试、是否 fail-closed）

### 2.4 关键数据契约（必须给 Schema 草案）
至少给出这些契约的“字段清单 + 字段解释 + 最小示例（JSON）”：
- TaskSpec（统一任务规格）
- StepSpec / StepResult（步骤规格与结果）
- Artifact（内容寻址、类型、安全标签、引用）
- Claim / EvidenceRef（断言与证据回指）
- PolicyDecision / GateResult（门禁决策与证据）
- RunRecord（一次运行的全链路记录）
- EvoMapSignal（从 AIOS 侧如何派生并对接 EvoMap）

### 2.5 端到端业务流（必须画出文字版时序）
至少覆盖：
1) 写报告端到端自动化（目的识别→证据装载→底稿→外发→复审→脱敏→发布）  
2) 做调研端到端自动化（含必要时的“辩论/交叉验证”）  
3) 需求漏斗闭环（碎片→分类→立项→分派→执行→交付）  
4) 自进化闭环（Signal→Plan→Approval→Execute→Quarantine/Rollback→Promote）  

每条流程都要标出：
- 关键输入
- 关键中间产物（artifact）
- 质量门禁点（Gate）
- 失败后的降级/重试/人工介入点

### 2.6 EvoMap 纳入方案（必须可执行）
- 你建议“桥接 openclaw 的 EvoMap”还是“AIOS 内复刻最小闭环”？给出理由与迁移策略。
- 具体到“AIOS 侧要产出哪些 signals、如何去重、如何分级、如何避免信号风暴、如何触发审批”。
- 守护条件：预算、审批、隔离、回滚、vendor fingerprint（如适用）。

### 2.7 多模型机制（辩论/仲裁/交叉验证）
- 明确触发条件（何时必须双模型/多模型）。
- 明确输入输出：每轮 debate 的产物是什么（Claim diff、冲突清单、替换块、风险条款）。
- 明确成本控制：token/时间/并发/冷却时的降级策略。

### 2.8 可执行路线图（必须给里程碑 + 验收标准）
- 给出 M0-M5（或你认为更合理的分期），每个里程碑：
  - 交付物（可点验的文件/功能/测试）
  - 验收标准（可量化/可回放）
  - 风险与对策
- 特别要求：先把“写报告端到端自动化”做到可稳定运行（减少手喂标准），再扩展到其他场景。

### 2.9 缺口清单与追问（用于下一轮迭代）
- 你认为我当前材料里还缺什么关键信息（最多 10 条，按优先级排序）。
- 给出 3-5 个最小澄清问题（我回答后你就能把方案从 v0 推进到 v1）。
- 给出下一轮我该如何追问你的“提示词模板”（用于 follow-up）。

## 3. 评分与通过标准（你需要给结论）

最后必须输出：
- 结论：通过 / 条件通过 / 不通过
- 若为条件通过/不通过：给出“必须补齐的 3-7 条”以及每条的完成标准。

---
## Source: REQUEST_aios_dual_deepresearch_R1_20260227.md
Path: /vol1/1000/projects/planning/aios/docs/specs/REQUEST_aios_dual_deepresearch_R1_20260227.md

---
title: REQUEST - AIOS 双 Deep Research 追问与查漏补缺 R1
date: 2026-02-27
audience: ChatGPT Deep Research + Gemini Deep Research
language: zh
---

# REQUEST：AIOS 双 Deep Research 追问与查漏补缺（R1）

你将收到一个最小材料包。材料里已经有两份高质量初答：

1) 平台级架构评审初答  
2) 深度研究选题与提示词初答

你的任务不是重复初答，而是做“深度追问与查漏补缺”。

## 0. 目标

请基于材料，输出一份可直接执行的“研究作战包”，用于我并行发起多轮 Deep Research。

目标是：
- 找出仍未被充分论证的关键决策点（高风险/高不确定性）
- 给出每个决策点的高质量 Deep Research 提示词
- 给出分轮执行顺序、验收标准、失败补救策略

## 1. 强约束

1) 全中文表达。  
2) 只按“文件名”引用，不输出本地路径。  
3) 不要重复材料里已经明确达成共识的内容；重点做“缺口、冲突、未证实假设”。  
4) 每个研究项必须给“可直接复制执行”的提示词（主提示词 + 追问提示词）。  
5) 必须覆盖这 5 条主链路：
- 平台数据契约与事件溯源
- 报告端到端自动化与质量门禁
- 需求漏斗闭环与项目治理
- 记忆/知识库双系统与证据链
- 多模型交叉验证与 EvoMap 自进化治理

## 2. 输出结构（必须按此标题）

### 2.1 一句话结论
- 说清最需要优先深挖的 3 个研究方向和原因。

### 2.2 初答对照后的“关键缺口清单”
- 先对比两份初答，列出：
  - 共识点（简述）
  - 冲突点
  - 空白点
- 输出一个表格：`缺口ID | 影响链路 | 风险等级 | 不解决后果 | 建议研究轮次`

### 2.3 Deep Research 研究包（6-10 个研究项）
- 每个研究项必须包含：
  - `研究项标题`
  - `要验证的假设`
  - `外部对照对象`（至少 3 类：标准/论文/工程实践/开源实现）
  - `主提示词（可直接运行）`
  - `追问提示词（可直接运行）`
  - `预期产物合同`（必须落成什么交付物）
  - `验收标准`（通过/不通过怎么判定）
  - `失败补救`（若拿不到足够证据，下一步怎么做）

### 2.4 分轮执行计划（R1-R3）
- R1/R2/R3 每轮：
  - 跑哪些研究项
  - 并行度建议
  - 每轮退出条件
  - 每轮产物落盘清单

### 2.5 可直接执行的总控 Prompt（用于编排器）
- 给我一段“总控提示词”，用于后续在编排器里自动驱动多轮 DR。
- 总控提示词里要包含：输入、步骤、门禁、输出契约、失败重试规则。


---
## Source: REQUEST_aios_deepresearch_prompt_planner_R0_20260227.md
Path: /vol1/1000/projects/planning/aios/docs/specs/REQUEST_aios_deepresearch_prompt_planner_R0_20260227.md

---
title: REQUEST - AIOS 深度研究选题与提示词生成（R0）
date: 2026-02-27
audience: ChatGPT Pro Extended（用于生成 Deep Research 提示词）
language: zh
---

# REQUEST：AIOS 深度研究选题与提示词生成（R0）

你将收到一个最小材料包（若干文件）。请基于这些文件内容，给出：

1) **AIOS 接下来最值得做 Deep Research 的选题清单**（优先级排序，说明原因与预期收益）。  
2) **每个选题对应的 Deep Research 提示词（prompt）**：我会把这些 prompt 逐条喂给 Deep Research 去跑研究与拿证据。

材料包文件清单（请只按文件名引用）：
- `AIOS_CONTEXT_DIGEST_R0_20260227.md`
- `AIOS_REQUIREMENTS_FULLVIEW_V5_20260227.md`
- `AIOS_PLATFORM_INFRA_DESIGN_V0_20260227.md`
- `AIOS_DEVELOPMENT_PLAN_20260226.md`
- `REPORT_SPEC_20260202.md`
- `PRO_REVIEW_LOOP_WORKFLOW_20260202.md`
- `REPORT_PURPOSE_MATRIX_20260208.md`
- `REPORT_TRIPLEKIT_PROMPTS_20260208.md`
- `REQ_FUNNEL_INPUT_V2_20260223.md`
- `PROJECT_GOVERNANCE_20260223.md`
- `PM_CHAIN_EXECUTION_V1_20260223.md`
- `OPENCLAW_EVOMAP_TYPES_20260226.ts`

## 0. 背景与目标（必须按此理解）

我要做的是“个人级基础设施底座（AIOS）”，目标不是只为某一个应用服务，而是能承载未来未知类别的各类应用，并且在运行中能自进化。

我已经有很多资产散落在多个仓库：报告方法论与提示词体系、KB/证据包/脱敏/发布工具链、HomeAgent/StoryPlay 应用、OpenClaw 的 EvoMap 与项目治理机制、以及 ChatgptREST 的多模型执行平台（但 AIOS 不改 ChatgptREST 代码，只调用）。

我现在需要你做的是：**识别哪些“关键决策/关键不确定性”必须依赖外部信息与系统性对照研究（Deep Research）才能做出高标准、可长期演进的架构决策**，并把它们转化为可直接运行的 Deep Research prompts。

## 1. 强约束（必须遵守）

1) 全中文表达（可以保留少量代码/字段名，但首次出现需给中文解释）。  
2) **只按文件名引用**：不要输出任何本地路径、目录名、盘符、URL（除非材料里已出现且必须引用）。  
3) 输出必须可执行：每个选题要给一个“可直接复制给 Deep Research 的提示词”，不要只给方向。  
4) 选题必须覆盖：报告端到端自动化、需求漏斗闭环、知识管理（记忆/KB）、多模型交叉验证/辩论机制、自进化闭环（EvoMap 相关）。  
5) 你不需要替我做研究结论；你要输出“研究题目 + 研究 prompt + 预期交付物契约 + 验收标准”。  

## 2. 你需要交付的内容（输出结构硬要求）

请按以下结构输出（不要改标题层级，方便我后续做替换块落地）：

### 2.1 一句话结论
- 用 1-2 句话说清：为了做出高标准 AIOS 架构决策，最该 Deep Research 的方向是什么、为什么。

### 2.2 选题总览（排序）
- 给出 6-10 个 Deep Research 选题（按 P0/P1/P2 排序）。
- 每个选题包含：`题目` / `要解决的决策` / `为什么必须 Deep Research` / `不做的代价` / `预期产出（可落地）`。

### 2.3 每个选题的 Deep Research Prompt（可直接复制运行）

对每个选题，输出一个独立的 prompt，必须包含以下小节（保持一致格式，便于批量运行）：

1) **角色设定**：你以什么身份研究（例如：平台架构师/可靠性工程师/知识管理专家）。  
2) **任务目标**：要回答哪些具体问题（用编号）。  
3) **必须对照的方案/范式**：至少 3 个（例如：事件溯源 vs 状态存储；工作流引擎选型；知识库双视图；多模型仲裁机制等）。  
4) **证据与来源要求**：要求引用公开来源并在结论处可回指（注明你希望它优先查哪类资料：论文/工程实践/标准/开源项目文档/工业案例）。  
5) **输出契约**：必须输出的结构（例如：结论/比较表/推荐方案/失败模式/边界条件/落地步骤/验收标准/风险与对策）。  
6) **与本地材料的对齐点**：明确它需要对齐材料包中的哪些文件（只写文件名），以及它要输出哪些“可替换块”供我落盘。  
7) **Follow-up Questions**：如果研究过程中发现信息不足，需要向我追问的 5-10 个问题（按优先级）。  

### 2.4 研究执行顺序与里程碑
- 你建议我先跑哪些选题（按周/按迭代），每个选题完成的“验收信号”是什么。

### 2.5 你认为材料包仍缺什么（仅列缺口，不要脑补）
- 列出 5-15 条你认为“缺了会导致研究结论偏差”的信息缺口，并标注：
  - 缺口是什么
  - 影响哪个选题
  - 我该从哪里补（例如：应补哪个系统的配置、或补一份台账、或补一次现网测量）


---
## Source: REQUEST_aios_pro_rerun_gapfill_R1_20260227.md
Path: /vol1/1000/projects/planning/aios/docs/specs/REQUEST_aios_pro_rerun_gapfill_R1_20260227.md

---
title: REQUEST AIOS Pro Rerun After Gap Fill R1
date: 2026-02-27
owner: planning-aios
---

你现在是 AIOS 的总架构顾问。我们已根据你上一轮缺口清单补齐资料包，请你基于完整材料重新给出“可执行且可落地”的全盘方案。

## 任务目标

1. 先核验：上一轮 15 条缺口哪些已关闭，哪些仍部分缺失，哪些仍需用户拍板。
2. 在核验基础上，输出 AIOS 全盘设计方案（不是只讲 kernel）：
   - 架构设计
   - 业务流程
   - 实现逻辑
   - 质量门禁
   - 需求漏斗
   - EvoMap 融合
   - 多模型交叉验证与成本治理
3. 输出“可执行路线图”，要求可直接拆解为开发 backlog。

## 关键约束

- 必须统筹 A/B/C/D 场景（尤其 A2 报告自动化、D2 漏斗、D3 EvoMap）。
- 基础设施优先，但要支持后续未知类别应用接入。
- 方案必须支持“运行中自进化”，并有明确审批与回滚边界。
- 不要泛泛建议，必须给结构化合同与字段建议。

## 输出格式（严格）

1) Gap Closure Review
- 表格：gap_id | status(closed/partial/open) | evidence_file | residual_risk | next_action

2) Target Architecture v1
- 分层架构图（文字化）
- 核心域对象与事件合同（建议字段）
- 模块边界与依赖关系

3) End-to-End Business Flows
- 报告自动化 6 步主链
- 需求漏斗全链路
- EvoMap 计划-审批-执行-审计链
- 每条流程给：输入/输出/门禁/失败处理

4) Implementation Blueprint
- 里程碑 M0-M6（每个里程碑包含：目标、交付物、完成标准、阻塞条件）
- backlog 拆分（P0/P1/P2）
- 测试矩阵（单测/集成/回归/故障演练）

5) Governance and Runtime Controls
- 副作用审批策略落地建议
- 成本与预算策略（按任务等级）
- 统一仪表盘最小可用模型（对接 Top20 queries）

6) Decision List For User
- 仅列“必须由用户拍板”的 5-10 个参数
- 每个参数说明影响范围与推荐默认值


---
## Source: REQUEST_memory_state_governance_pro_R1_20260227.md
Path: /vol1/1000/projects/planning/aios/docs/specs/REQUEST_memory_state_governance_pro_R1_20260227.md

---
title: REQUEST Memory and State Governance for Agent System R1
date: 2026-02-27
owner: planning-aios
---

你是我的“Agent 体系治理架构师”，不是代码助手。重点是：如何长期管理记忆、状态、更新节奏、验收与回滚，确保多个 agent 并行工作时不失真、不漂移。

## 背景

- 我已在多个仓库和 workspace 并行推进（planning/openclaw/openclaw-workspaces/pm/kb/maint 等）。
- 当前痛点不是“能不能写脚本”，而是：
  1) 记忆与状态更新如何形成可持续治理机制；
  2) 多条线（KB/CodingTeam/Auth/Advisor/PM）如何统一口径并持续更新；
  3) 给 Pro 的快照包如何标准化，既高信号又可追溯。

## 你的任务（必须按顺序）

1. 对包内现状做“治理诊断”：找出当前记忆治理的结构性风险与信息漂移风险。
2. 给出一套“非脚本中心”的治理体系：
   - 角色与责任（Owner/Auditor/Integrator/Publisher）
   - 状态机（草稿/候选/生效/归档/废弃）
   - 单一真相源 SoT 分层
   - 更新节奏（日更/周更/月更）
   - 变更门禁与验收
3. 给出“快照打包标准 v1”：
   - 必带文件清单
   - 证据最小集合
   - 脱敏与安全边界
   - 包质量评分规则（什么样的包算高质量）
4. 给出“Agent 运行治理协议 v1”：
   - 任务交接协议
   - 上下文压缩与反压缩协议
   - 冲突解决协议
   - 回滚与应急协议
5. 输出可执行方案：
   - 30 天落地计划（按周）
   - P0/P1/P2 action list
   - 每项 action 的完成标准

## 强约束

- 不能只给“写脚本自动化”的方案；脚本只能是治理体系里的执行器。
- 必须结合包内真实状态（包括 dirty worktree、未提交总结文档、feishu intake 未见新会话证据）。
- 必须给“可审计字段合同”，而不是抽象建议。

## 输出格式（严格）

1) 现状诊断
- 表格：问题 | 证据文件 | 风险等级 | 根因 | 影响范围

2) Memory Governance Model v1
- 角色-职责矩阵
- 状态机定义
- SoT 分层与优先级

3) Snapshot Packaging Standard v1
- 标准目录结构
- 必带文件清单
- 包质量评分（0-100）与扣分项

4) Agent Operational Protocol v1
- 交接协议
- 更新协议
- 冲突协议
- 回滚协议

5) 30-Day Execution Plan
- Week1..Week4，每周目标/动作/产物/验收标准

6) Decision Checklist For Me
- 需要我拍板的 8-12 个参数（含建议默认值）


---
## Source: REQUEST_memory_state_governance_pro_R2_inline_20260227.md
Path: /vol1/1000/projects/planning/aios/docs/specs/REQUEST_memory_state_governance_pro_R2_inline_20260227.md

---
title: REQUEST Memory and State Governance for Agent System R2 Inline Contract
date: 2026-02-27
owner: planning-aios
---

你是“Agent 体系治理架构师”。

这是 R2 提问，R1 失败原因是附件不可读。为避免再次失败，本次把合同正文内嵌在问题中：
- 不论附件是否可读，你都必须以本问题中的“合同正文”为唯一输出合同。
- 附件只作证据补充，不得替代合同。

## 合同正文（唯一合同）

### 背景
- 多仓并行推进：planning/openclaw/openclaw-workspaces/pm/kb/maint。
- 主要痛点：
  1) 记忆与状态更新如何形成可持续治理机制；
  2) KB/CodingTeam/Auth/Advisor/PM 多线如何统一口径并持续更新；
  3) 给 Pro 的快照包如何标准化，做到高信号且可追溯。

### 任务顺序（必须按序）
1. 现状治理诊断：定位结构性风险与信息漂移风险。
2. 非脚本中心治理体系：
   - 角色与责任（Owner/Auditor/Integrator/Publisher）
   - 状态机（草稿/候选/生效/归档/废弃）
   - SoT 分层
   - 更新节奏（日更/周更/月更）
   - 变更门禁与验收
3. 快照打包标准 v1：
   - 必带文件
   - 证据最小集合
   - 脱敏边界
   - 包质量评分规则
4. Agent 运行治理协议 v1：
   - 交接协议
   - 上下文压缩与反压缩协议
   - 冲突解决协议
   - 回滚与应急协议
5. 可执行方案：
   - 30 天落地计划（按周）
   - P0/P1/P2 action list
   - 每项 action 完成标准

### 强约束
- 不能只给“脚本自动化”方案；脚本只能是执行器。
- 必须结合真实状态：
  - dirty worktree 与未提交总结文档；
  - feishu intake 路由已修但尚无新会话增长证据；
  - PM/KB workspace 存在审计噪音。
- 必须给“可审计字段合同”，避免抽象空话。

### 输出格式（严格）
1) 现状诊断：表格（问题 | 证据文件 | 风险等级 | 根因 | 影响范围）
2) Memory Governance Model v1：角色职责矩阵、状态机定义、SoT 分层与优先级
3) Snapshot Packaging Standard v1：目录结构、必带文件清单、包质量评分（0-100）与扣分项
4) Agent Operational Protocol v1：交接协议、更新协议、冲突协议、回滚协议
5) 30-Day Execution Plan：Week1..Week4（目标/动作/产物/验收标准）
6) Decision Checklist For Me：8-12 个需我拍板参数（含建议默认值）

## 证据锚点（必须引用）
- SoT 统一口径：`SOT_CONSOLIDATED_STATUS_2026-02-26.md`
- KB 验收：`SOT_KB_ARCHIVE_ACCEPTANCE_REPORT_2026-02-25.md`
- PM 在途：`SOT_PM_PROJECT_PORTFOLIO_V2.md` `SOT_PM_PROJECT_STATUS.md` `SOT_PM_DISPATCH_QUEUE.md`
- 线级总结：`LINE_PM_SESSION_EXEC_SUMMARY_2026-02-26.md` `LINE_KB_FULL_WORK_SUMMARY_2026-02-26.md` `LINE_CODINGTEAM_COMPLETION_SUMMARY_2026-02-26.md` `LINE_CHATGPTADVISOR_SUMMARY_2026-02-26.md` `LINE_MAINT_AUTH_SWITCH_2026-02-26.md`

## 质量门槛（自检后再输出）
- Q1: 每个关键判断是否有证据文件回指？
- Q2: 每个协议是否包含“字段合同 + 触发条件 + 责任角色 + 验收证据”？
- Q3: 30 天计划是否可执行并可验收？


---
## Source: redteam_comparison_summary_20260227.md
Path: /vol1/1000/projects/planning/aios/docs/specs/redteam_dual_review_20260227/redteam_comparison_summary_20260227.md

# Redteam 双模型对照摘要 2026-02-27

## 作业与来源
- ChatGPT Pro 红方：`78476c026f8444ccbec354c7a31d380f`
- Gemini Deep Think 红方：`c4ff60b7fb1c4dd4ac7e23cc44461b79`

## 共同高风险结论
1. ArtifactStore 持久化一致性和溯源语义存在根基级风险（伪持久/溯源覆盖）。
2. SoT 实现存在偏差：运行事实与文件产物未完全收敛到事件+工件链路。
3. 门禁 fail-closed 未落地到执行时序：存在“先写盘后门禁”或未知标签放行风险。
4. 长时阻塞/needs_human/慢门禁会导致并发吞吐崩溃，需挂起-重水合机制。
5. 报告链路时间约束冲突（60s 阶段超时 vs 61s 外部节流）未被工程化解决。
6. 纯 Markdown 替换链路不稳，需结构化块替换（AST/Block JSON）与 digest 校验。
7. EvoMap 不能直接自动执行，需先走 plan-only + 审批 + 审计回流。

## 主要分歧与互补
1. Pro 更强调“证据链闭合/契约缺失”是首要阻塞，主张先补最小治理包再推进业务层。
2. Gemini 更强调“运行时并发/资源协调/分布式锁”与“连接器背压”风险，偏工程失效模式。
3. Pro 对路线图重排更细：建议先地基修复，再做 Funnel/EvoMap 规模化接入。
4. Gemini 对模型治理更激进：强调模型毒化、自动化偏见与回滚断点要前置。

## 合并后的优先序（建议）
1. P0 地基修复：ArtifactStore 事务与溯源模型、门禁时序、security_label fail-closed。
2. P0 运行治理：StepWorker + Checkpoint + Rehydration，明确挂起释放资源。
3. P0 契约落盘：SchemaRegistry 最小契约包（REPORT_SPEC/TaskSpec/RunRecord/GateResult/EvoMap signal）。
4. P1 连接器治理：ChatgptREST 限流/背压/预算策略，修复 60s vs 61s 死锁。
5. P1 文档链路治理：Block JSON 工作态 + 发布态渲染，替换纯文本 patch。
6. P1 EvoMap 接入：先 plan-only，执行必须审批，审计链闭环后再考虑低风险自动执行。

## 下一步建议
- 以本摘要为输入，再发一轮“统一裁决 prompt”，要求输出单一执行蓝图（含删减项与冻结项）。

---
## Source: answer.md
Path: /vol1/1000/projects/planning/aios/docs/specs/arch_review_R1_20260227/20260227_job_585d1b590e614c1297c79e8ed8b48c3b/answer.md

### 2.1 一句话结论

* AIOS 平台级架构应以**“契约优先 + 事件溯源 + 内容寻址工件库 + 强制门禁”**为核心，采用微内核（Kernel）把方法论固化为可自动执行的管线与可审计的质量闭环。
* **先把“写报告端到端自动化”做成稳定可回放的标杆流水线**（以 `REPORT_SPEC_20260202.md` 为单一事实源、以 `REPORT_TRIPLEKIT_PROMPTS_20260208.md`/`REPORT_PURPOSE_MATRIX_20260208.md` 固化结构与门槛），同时打通 EvoMap 信号→计划→审批→执行→隔离/回滚→晋级的最小闭环，为后续调研与需求漏斗提供同一套平台原语。

---

### 2.2 需求全景再拆解（用你自己的话重述，但不新增需求）

> 基于 `AIOS_REQUIREMENTS_FULLVIEW_V5_20260227.md` 与 `AIOS_PLATFORM_INFRA_DESIGN_V0_20260227.md`，按“平台能力/应用能力”两层重述；不新增需求，只做结构化拆解与优先级标注。

#### 平台能力（Platform Capabilities）

1. **统一任务规格与编排执行**

* 需要一个统一的 TaskSpec（统一任务规格）贯穿从入口→路由→步骤执行→产物→门禁→复盘。
* 管线执行框架要支持：步骤编排、重试、幂等、资源互斥、预算控制、可恢复长任务、落盘与回放（`AIOS_PLATFORM_INFRA_DESIGN_V0_20260227.md`）。

2. **证据与工件治理（可追溯、可回指）**

* 需要内容寻址的 Artifact（工件）与 EvidenceRef（证据回指）体系：证据包、底稿、外发稿、复审替换块、发布清单等都必须落盘、可引用、可重算（`AIOS_PLATFORM_INFRA_DESIGN_V0_20260227.md`、`REPORT_SPEC_20260202.md`）。

3. **质量门禁与审计（把“手喂标准”变成系统强制）**

* 需要结构/交付/成本/安全/claim-evidence（断言-证据）门禁（`AIOS_PLATFORM_INFRA_DESIGN_V0_20260227.md`）。
* 复审必须是可运行流程：输出“结论（通过/条件通过/不通过）+ 冲突清单 + 可直接粘贴的替换块”，而不是泛泛建议（`PRO_REVIEW_LOOP_WORKFLOW_20260202.md`、`REPORT_TRIPLEKIT_PROMPTS_20260208.md`）。

4. **多模型交叉验证/辩论（在需要时强制执行）**

* 多模型不是“建议”，而是可触发、可回放、可审计的步骤：产出冲突清单、替换块、风险条款与成本记录（`AIOS_REQUIREMENTS_FULLVIEW_V5_20260227.md`、`AIOS_PLATFORM_INFRA_DESIGN_V0_20260227.md`）。

5. **自进化闭环（EvoMap 硬需求）**

* AIOS 运行中要能派生 signals，送入 EvoMap 生成 evolution plan，并在审批/预算/隔离/回滚机制下执行（`AIOS_PLATFORM_INFRA_DESIGN_V0_20260227.md`、`OPENCLAW_EVOMAP_TYPES_20260226.ts`）。

#### 应用能力（Application Capabilities）

A 类（工作自动化与研究输出）

* **A2 写报告端到端自动化**：目的识别→证据装载→内部底稿→外发沟通稿→Pro 复审→脱敏→发布（`AIOS_REQUIREMENTS_FULLVIEW_V5_20260227.md`）。
* **A3 做调研端到端自动化**：范围定义→检索→补充→综合分析→必要时辩论/交叉验证→出稿→入库（`AIOS_REQUIREMENTS_FULLVIEW_V5_20260227.md`）。

D 类（AIOS 自身）

* **D2 需求漏斗闭环**：碎片→分类→立项→分派→执行→交付（`AIOS_REQUIREMENTS_FULLVIEW_V5_20260227.md`）。
* **D3 EvoMap**：先模板后模型、可运行的自进化闭环（`AIOS_REQUIREMENTS_FULLVIEW_V5_20260227.md`、`AIOS_PLATFORM_INFRA_DESIGN_V0_20260227.md`）。
* **D1+D4 多模型**：辩论与交叉验证机制（`AIOS_REQUIREMENTS_FULLVIEW_V5_20260227.md`）。

C 类（应用开发）

* 激励系统后端、HomeAgent 增强等（`AIOS_REQUIREMENTS_FULLVIEW_V5_20260227.md`）。

#### P0 / P1 / P2（含理由）

* **P0（先做，必须先跑通）**

  1. 写报告端到端自动化稳定运行：这是“规格驱动工作流”的最小闭环样例，且材料表明你“零件齐全，只缺编排器与门禁固化”（`AIOS_REQUIREMENTS_FULLVIEW_V5_20260227.md`）。
  2. 平台原语补齐：TaskSpec/StepSpec/RunRecord/Artifact/PolicyGate/EvidenceRef 的统一契约 + 事件落盘 + 可回放。没有这些，无法把“标准”固化为系统能力（`AIOS_PLATFORM_INFRA_DESIGN_V0_20260227.md`）。
  3. EvoMap 最小接入：至少做到**信号派生 + 去重分级 + 风暴抑制 + 需要审批的计划进入待审队列**，为后续自进化闭环奠基（`AIOS_PLATFORM_INFRA_DESIGN_V0_20260227.md`、`OPENCLAW_EVOMAP_TYPES_20260226.ts`）。

* **P1（第二阶段，复用 P0 的平台能力扩展场景）**

  1. 调研端到端自动化（含必要时的辩论/交叉验证）——复用证据包、claim-evidence、复审与落盘机制。
  2. 需求漏斗闭环——将碎片收集与执行交付纳入同一 TaskSpec/RunRecord 体系。
  3. 多模型机制工程化（触发条件、产物、成本控制、降级策略）——从“能力”变“流程”。

* **P2（后续扩展）**

  * 激励系统后端、HomeAgent 增强、投研/知识图谱等：可在平台稳定后作为 Apps 持续接入（`AIOS_REQUIREMENTS_FULLVIEW_V5_20260227.md`）。

---

### 2.3 平台分层与模块边界（必须给清单）

#### 2.3.1 分层职责与“禁止做什么”

**Kernel（内核层）**

* 职责：

  * 定义并强制执行核心契约：TaskSpec/Artifact/RunRecord 等 schema 校验与版本化。
  * 事件溯源与不可变事实：EventLog（append-only）、工件存储（内容寻址）、门禁引擎、资源互斥、幂等与副作用登记。
* 禁止：

  * **禁止承载任何具体业务流程**（写报告/调研/漏斗都是 Apps）。
  * **禁止直连外部系统**（外部调用必须经 Connector），禁止在 Kernel 内写 prompt 与业务模板。
  * 禁止绕过门禁直接产生“可外发/可写入”的副作用。

**Runtime（运行时层）**

* 职责：

  * 调度与执行：Pipeline/Graph Runner、重试、并发、checkpoint、预算治理、队列与优先级。
  * 生成可回放视图：RunRecord、ArtifactGraph 等从 EventLog 派生的可查询视图。
  * 路由：把 TaskSpec 映射到 pipeline（报告/调研/漏斗/自进化相关）。
* 禁止：

  * 禁止把某个应用逻辑写死在 Runtime；Runtime 只执行“被注册的 pipeline 与 capability”。
  * 禁止绕过 Kernel 的事件与工件落盘；所有输入/输出必须可追溯。

**Connector（连接器层）**

* 职责：

  * 适配外部系统：证据包生成、脱敏、发布、多模型服务、EvoMap hub 等，提供**稳定、可测试、可模拟**的接口。
  * 将外部交互结果标准化为 Artifact/StepResult，确保可追溯与可回放（至少能回放到“输入与产出一致”）。
* 禁止：

  * 禁止在 Connector 内做业务决策（例如“是否可外发”“是否通过”）；Connector 只提供能力与标准化结果。
  * 禁止私自落盘到 Kernel 不可见的位置（必须通过 ArtifactStore）。

**Apps（应用层）**

* 职责：

  * 定义场景化 pipeline：report_pipeline、research_pipeline、intake_pipeline、evolution_pipeline 等。
  * 管理业务模板与模块库：目的矩阵、双轨出稿、复审提示词等，形成可复用的“替换块”体系（`REPORT_PURPOSE_MATRIX_20260208.md`、`REPORT_TRIPLEKIT_PROMPTS_20260208.md`）。
* 禁止：

  * 禁止直接访问底层数据库/文件系统；必须通过 Kernel API（EventLog/ArtifactStore/PolicyGate）与 Connector。
  * 禁止产生未经过 Gate 的副作用（发布、写入、执行命令、覆盖文件等）。

---

#### 2.3.2 核心模块清单（含输入输出/依赖/失败语义）

> 说明：字段级输入输出在此给“关键字段”；完整 Schema 在 2.4。模块间通信以 2.4 的契约为准。

下面按“必须有的最小平台闭环”给出建议模块边界（覆盖 `AIOS_PLATFORM_INFRA_DESIGN_V0_20260227.md` 已有原语，并补齐缺口）。

---

##### 模块 A：TaskSpecService（任务规格服务）

* 输入（关键字段）：

  * `raw_query`（原始请求文本）、`intent_hint`（可选意图提示）、`report_spec_ref`（可选，指向 REPORT_SPEC.yaml 的 artifact_id）
  * `sources.scope`（来源范围）、`context.distribution`（internal/external）、`evidence.level`、`requirements.detail_level`
  * `risk_level`、`budget`（maxRunSeconds/maxToolCalls/maxTokens）
* 输出：

  * `TaskSpec`（补全标准字段，如 `task_id`、`created_at`、`normalized_query`、`policy_profile`、`idempotency_key`）
* 依赖：

  * SchemaRegistry（契约注册表）、PolicyEngine（最小可运行约束：例如外发必须 external 分发、来源范围必须显式）
  * EventLog（记录 task.created）、ArtifactStore（如果内含 spec 文件则存为 artifact）
* 失败语义：

  * **校验失败：fail-closed**（不创建 run），写入 `task.rejected` 事件，产出 `GateResult` 说明缺什么字段/违反什么约束；不重试，要求人工补齐输入。

---

##### 模块 B：PipelineRegistry（管线注册表）

* 输入：

  * `PipelineDef`（pipeline_id、版本、steps[]、默认 gate_profile、所需 resources）
* 输出：

  * 可被 Router 查询的 `PipelineIndex`（按 intent/purpose/distribution 匹配）
* 依赖：

  * SchemaRegistry、EventLog（registry.updated）
* 失败语义：

  * 定义不合法：fail-closed（不注册），落盘 `registry.reject`；需人工修正。

---

##### 模块 C：Router（路由器）

* 输入（关键字段）：

  * `TaskSpec.intent`、`TaskSpec.report_spec_ref`、`TaskSpec.context.distribution`、`TaskSpec.sources.scope`
  * （报告场景）`purpose` 尚未识别时：先走“purpose_identify”子路由
* 输出：

  * `RouteDecision`：`pipeline_id`、`reason_codes[]`、`requires_human_confirm`、`suggested_questions[]`
* 依赖：

  * PipelineRegistry
  * （报告）PurposeMatrixRegistry（从 `REPORT_PURPOSE_MATRIX_20260208.md` 固化为可机读 registry）
  * （报告）ReportSpecParser（从 `REPORT_SPEC_20260202.md` 要求的 `REPORT_SPEC.yaml` 字段读取 scope/distribution/evidence）
* 失败语义：

  * 无匹配：fail-closed，写 `route.failed` 事件，返回 `GateResult`（列出可选 pipeline 与缺失字段）。
  * 多匹配：**挂起等待人工确认**（`requires_human_confirm=true`），不自动选。

---

##### 模块 D：Scheduler（调度器）

* 输入：

  * `TaskSpec` + `RouteDecision.pipeline_id` + `priority`（由 risk/urgency 派生）
* 输出：

  * `run_id`（创建 RunRecord 的唯一标识），入队 `run.queued`
* 依赖：

  * ResourceManager（并发/互斥）、EventLog
* 失败语义：

  * 资源不足：进入 `run.queued` 并等待；若超时，写 `run.wait_timeout` 并触发降级策略（见后述）。

---

##### 模块 E：PipelineRunner（管线执行器）

* 输入：

  * `TaskSpec`、`PipelineDef.steps[]`
* 输出：

  * `RunRecord`（最终状态）+ 每步 `StepResult` + artifacts/claims/gates
* 依赖：

  * EventLog（记录 step.started/step.completed/step.failed）
  * ArtifactStore（存产物）
  * PolicyGate（每步前/后、关键节点）
  * IdempotencyStore（幂等键→结果复用）
  * ConnectorManager（调用外部能力）
* 失败语义（必须明确）：

  * **可重试失败**（transient，例如外部调用超时/限流）：按 `retry_policy` 重试，重试过程每次落盘 event；超过上限→标记 step.failed（error_category=transient_exhausted）。
  * **不可重试失败**（policy_block / schema_invalid / security_block）：立即 fail-closed，写入 GateResult，run 结束为 failed 或 needs_human（视 gate 决策）。
  * **质量失败**（quality_block，例如 claim-evidence 不达标）：允许一次“自修复重试”（使用审计/修复提示词生成替换块），仍失败→needs_human。

---

##### 模块 F：RunRecordBuilder（运行记录构建器）

* 输入：

  * EventLog 中与 `run_id` 相关的事件流
* 输出：

  * `RunRecord`（步骤列表、产物列表、门禁结果、成本指标、人工介入点）
* 依赖：

  * EventLog、SchemaRegistry
* 失败语义：

  * 视图构建失败不影响事实源（EventLog），但会输出 `runrecord.build_failed` 并提供降级：返回“最小 run 摘要”（只含 event span 与最后错误）。

---

##### 模块 G：ArtifactStore（工件库）

* 输入：

  * `bytes` + `ArtifactMeta`（type/mime/security_label/provenance）
* 输出：

  * `artifact_id`（内容寻址：sha256）
* 依赖：

  * Hash（sha256）、EventLog（artifact.created）
* 失败语义：

  * 写入失败：step 直接失败（因为产物不可追溯）；允许重试（原子写入），若反复失败触发 EvoMap 信号（storage_unstable）。

---

##### 模块 H：ArtifactGraph（工件图谱）

* 输入：

  * `Artifact.references[]` + `EvidenceRef.artifact_id` + `StepResult.artifacts_out`
* 输出：

  * `ArtifactGraphView`（有向图：产物依赖、证据回指、替换块应用关系）
* 依赖：

  * ArtifactStore（metadata）、EventLog（引用边由事件或产物元数据提供）
* 失败语义：

  * 构建失败不阻断主流程，但会记录 `artifactgraph.lagging`；在审计/回放场景必须可补算。

---

##### 模块 I：PolicyGate（门禁统一入口）/ PolicyEngine（门禁引擎）

* 输入：

  * `GateRequest`：`gate_name`、`TaskSpec`、`StepSpec/StepResult`、相关 `Artifact/Claim/EvidenceRef`
* 输出：

  * `GateResult`/`PolicyDecision`：allow/warn/block/needs_human + 理由 + 证据回指 + 需要执行的修复动作（如“生成替换块”）
* 依赖：

  * 规则库（结构/交付/成本/安全/claim-evidence）
  * （可选）多模型审计能力（当 gate 配置为必须交叉验证）
* 失败语义：

  * 门禁自身故障：对高风险动作（发布/写入/执行）**默认 fail-closed**；对低风险只读动作可降级为 warn 并标注“不可信门禁状态”。

---

##### 模块 J：Memory（记忆门面）/ MemoryManager（记忆管理器）

* 输入：

  * `MemoryReadRequest`：query、scope（provided-only/web-ok-with-citations）、top_k、filters（tag/security）
  * `MemoryWriteRequest`：artifact_id、索引字段、security_label、requires_approval
* 输出：

  * `EvidencePack`（证据包 artifact）或检索结果列表（artifact_id + 摘要 + EvidenceRef）
* 依赖：

  * KB 相关 Connector（pack/query/redact）
  * PolicyGate（写入与敏感信息）
* 失败语义：

  * 读失败：可降级为“空证据包 + 待确认清单”，但必须在 RunRecord 中标注 evidence.level 下降；
  * 写失败：fail-closed（避免半写入），触发 EvoMap 信号（kb_write_failed）。

---

##### 模块 K：ConnectorManager（连接器管理器）

* 输入：

  * `ConnectorCall`：connector_name、params、budget、idempotency_key
* 输出：

  * 标准化 `ConnectorResult`（ok/failed + artifact_out + logs）
* 依赖：

  * 各 connector 实现（KB、发布、多模型、EvoMap）
* 失败语义：

  * 外部系统失败：按 error_category 分类（transient/permanent/auth/policy）；transient 可重试；auth/permanent 不重试并需要人工介入。

---

##### 模块 L：MultiModelRunner（多模型执行器）/ DebateOrchestrator（辩论编排器）

* 输入：

  * `DebateSpec`（由 TaskSpec + Gate 触发生成）：议题、证据包、需要验证的 claims、角色分配、轮次、预算
* 输出：

  * `DebateResult`（冲突清单、替换块、风险条款、成本统计）作为 artifact，并回填到 GateResult（作为决策证据）
* 依赖：

  * ChatgptRESTConnector（多模型调用统一入口，见 `AIOS_PLATFORM_INFRA_DESIGN_V0_20260227.md` 的约束）
  * PolicyGate（成本/时间/并发限制）
* 失败语义：

  * 预算不足：降级为“单模型 + 强审计模式 + 只输出冲突清单与待确认项”；
  * 多模型输出不可解析：标记为 needs_human，保留原始输出 artifact 供复盘。

---

##### 模块 M：EvoMapBridge（自进化桥接器）

* 输入：

  * `EvoMapSignal`（从 AIOS 事件/门禁派生），以及从 EvoMap fetch 的 plan/run/events
* 输出：

  * 信号发布结果、待审批队列、执行记录、隔离/回滚/晋级结果，全部落为 artifacts + events
* 依赖：

  * EvoMapConnector（对接 `OPENCLAW_EVOMAP_TYPES_20260226.ts` 的接口模型）
  * PolicyGate（审批/预算/隔离）
* 失败语义：

  * EvoMap 不可用：AIOS 仍可运行主业务流程，但把 signals 落盘并进入“待同步”队列；
  * 执行动作失败：自动触发 quarantine（隔离）并生成 rollback 计划（需要审批/或按策略自动回滚）。

---

### 2.4 关键数据契约（必须给 Schema 草案）

> 统一约定：以下字段名采用 snake_case（便于落地到 Python/JSON）；首次出现的英文名后给中文解释。示例 JSON 为“最小可用”，实际可扩展但需版本化。

---

#### 2.4.1 TaskSpec（统一任务规格）

**字段清单 + 解释**

| 字段                        | 类型              | 必填 | 解释                                                                  |
| ------------------------- | --------------- | -: | ------------------------------------------------------------------- |
| task_id                   | string          |  ✅ | 任务唯一标识（建议 UUID）                                                     |
| created_at                | string(ISO8601) |  ✅ | 创建时间                                                                |
| raw_query                 | string          |  ✅ | 用户原始请求（永不丢失）                                                        |
| normalized_query          | string          |  ✅ | 归一化后的任务描述（用于路由/检索）                                                  |
| intent                    | string          |  ✅ | 意图：report/research/funnel/evolution/…（可扩展）                          |
| audience                  | string          |  ⭕ | 受众描述（例如“领导/跨部门/自用”）                                                 |
| context                   | object          |  ✅ | 上下文边界（含分发与语言等）                                                      |
| context.distribution      | string          |  ✅ | internal / external（对应 `REPORT_SPEC_20260202.md`）                   |
| sources                   | object          |  ✅ | 来源范围约束                                                              |
| sources.scope             | string          |  ✅ | provided-only / web-ok-with-citations（对应 `REPORT_SPEC_20260202.md`） |
| requirements              | object          |  ✅ | 输出要求                                                                |
| requirements.detail_level | string          |  ✅ | brief / standard / full（对应 `REPORT_SPEC_20260202.md`）               |
| evidence                  | object          |  ✅ | 证据门槛                                                                |
| evidence.level            | string          |  ✅ | high / medium / low（对应 `REPORT_SPEC_20260202.md`）                   |
| risk_level                | string          |  ✅ | low / medium / high（用于审批与 fail-closed）                              |
| budget                    | object          |  ✅ | 预算与护栏                                                               |
| budget.max_run_seconds    | number          |  ✅ | 最大运行秒数                                                              |
| budget.max_tool_calls     | number          |  ✅ | 最大工具调用次数                                                            |
| budget.max_tokens         | number          |  ✅ | 最大 token（模型成本）                                                      |
| report_spec_ref           | string          |  ⭕ | 报告规格引用（建议为 REPORT_SPEC.yaml 的 artifact_id）                          |
| tags                      | string[]        |  ⭕ | 标签（场景/项目/主题）                                                        |
| idempotency_key           | string          |  ✅ | 幂等键：同一输入避免重复副作用                                                     |
| policy_profile            | string          |  ✅ | 门禁策略档位（例如 strict_external / standard_internal）                      |

**最小示例（JSON）**

```json
{
  "task_id": "task_8f3c1d2a",
  "created_at": "2026-02-27T10:15:30Z",
  "raw_query": "写一份关于XX的报告，发给领导",
  "normalized_query": "生成XX主题的对外沟通报告并可发布",
  "intent": "report",
  "audience": "领导/跨部门",
  "context": {
    "distribution": "external",
    "language": "zh"
  },
  "sources": {
    "scope": "provided-only"
  },
  "requirements": {
    "detail_level": "standard"
  },
  "evidence": {
    "level": "high"
  },
  "risk_level": "high",
  "budget": {
    "max_run_seconds": 900,
    "max_tool_calls": 120,
    "max_tokens": 180000
  },
  "report_spec_ref": "art_sha256_4c2b...e91",
  "tags": ["report", "xx项目"],
  "idempotency_key": "idem_3e6a...b11",
  "policy_profile": "strict_external"
}
```

---

#### 2.4.2 StepSpec / StepResult（步骤规格与结果）

##### StepSpec（步骤规格）

| 字段                   | 类型       | 必填 | 解释                                        |
| -------------------- | -------- | -: | ----------------------------------------- |
| step_id              | string   |  ✅ | 步骤唯一标识                                    |
| name                 | string   |  ✅ | 步骤名（purpose_identify / evidence_load / …） |
| capability           | string   |  ✅ | 能力块标识（与 Registry 对应）                      |
| inputs               | object   |  ✅ | 输入（引用 artifacts 或从 TaskSpec 派生）           |
| inputs.artifact_refs | string[] |  ⭕ | 输入工件列表（artifact_id）                       |
| params               | object   |  ⭕ | 参数（例如目的矩阵档位、模板名）                          |
| model                | object   |  ⭕ | 模型配置（若该 step 需要模型）                        |
| retry_policy         | object   |  ✅ | 重试策略                                      |
| timeout_seconds      | number   |  ✅ | 超时                                        |
| idempotency_key      | string   |  ✅ | 步骤幂等键（建议由 task_id+step_id+关键输入 hash）      |
| gate_profile         | string   |  ✅ | 门禁档位（决定 pre/post gates）                   |

##### StepResult（步骤结果）

| 字段            | 类型       | 必填 | 解释                                         |
| ------------- | -------- | -: | ------------------------------------------ |
| step_id       | string   |  ✅ | 对应 StepSpec.step_id                        |
| status        | string   |  ✅ | succeeded / failed / skipped / needs_human |
| started_at    | string   |  ✅ | 开始时间                                       |
| ended_at      | string   |  ✅ | 结束时间                                       |
| attempts      | number   |  ✅ | 尝试次数                                       |
| artifacts_out | string[] |  ✅ | 产物 artifact_id 列表                          |
| claims_out    | string[] |  ⭕ | 断言 claim_id 列表                             |
| gate_results  | string[] |  ✅ | gate_result_id 列表                          |
| metrics       | object   |  ✅ | 成本与资源统计                                    |
| error         | object   |  ⭕ | 错误信息（含分类）                                  |

**最小示例（JSON）**

```json
{
  "step_id": "step_02_evidence_load",
  "status": "succeeded",
  "started_at": "2026-02-27T10:16:10Z",
  "ended_at": "2026-02-27T10:16:40Z",
  "attempts": 1,
  "artifacts_out": ["art_sha256_a1b2..."],
  "claims_out": [],
  "gate_results": ["gate_7c91..."],
  "metrics": {
    "tool_calls": 3,
    "token_used": 0,
    "elapsed_ms": 30000
  }
}
```

---

#### 2.4.3 Artifact（内容寻址、类型、安全标签、引用）

| 字段                       | 类型       | 必填 | 解释                                                                                                       |
| ------------------------ | -------- | -: | -------------------------------------------------------------------------------------------------------- |
| artifact_id              | string   |  ✅ | 工件 ID（建议 `sha256:<hex>` 或内部规范化前缀）                                                                        |
| sha256                   | string   |  ✅ | 内容哈希（内容寻址核心）                                                                                             |
| type                     | string   |  ✅ | 工件类型：report_spec / evidence_pack / internal_draft / external_draft / review_patch / publish_manifest / … |
| mime                     | string   |  ✅ | 内容格式：text/markdown、application/json 等                                                                    |
| size_bytes               | number   |  ✅ | 大小                                                                                                       |
| created_at               | string   |  ✅ | 创建时间                                                                                                     |
| producer                 | object   |  ✅ | 产物来源                                                                                                     |
| producer.run_id          | string   |  ✅ | 产生该工件的 run                                                                                               |
| producer.step_id         | string   |  ✅ | 产生该工件的 step                                                                                              |
| security                 | object   |  ✅ | 安全与分发                                                                                                    |
| security.label           | string   |  ✅ | internal / external / secret（可扩展）                                                                        |
| security.tags            | string[] |  ⭕ | 例如 pii_possible / no_internal_trace_required                                                             |
| references               | object   |  ⭕ | 引用关系                                                                                                     |
| references.artifact_refs | string[] |  ⭕ | 依赖的上游工件                                                                                                  |
| evidence_refs            | string[] |  ⭕ | 支撑该工件的 EvidenceRef 列表（引用 ID）                                                                             |

**最小示例（JSON）**

```json
{
  "artifact_id": "sha256:9f1c...aa02",
  "sha256": "9f1c...aa02",
  "type": "internal_draft",
  "mime": "text/markdown",
  "size_bytes": 48231,
  "created_at": "2026-02-27T10:20:12Z",
  "producer": { "run_id": "run_12ab", "step_id": "step_03_internal_draft" },
  "security": { "label": "internal", "tags": ["contains_evidence_index"] },
  "references": { "artifact_refs": ["sha256:a1b2...c3d4"] },
  "evidence_refs": ["ev_01", "ev_02"]
}
```

---

#### 2.4.4 Claim / EvidenceRef（断言与证据回指）

##### Claim（断言）

| 字段            | 类型       | 必填 | 解释                               |
| ------------- | -------- | -: | -------------------------------- |
| claim_id      | string   |  ✅ | 断言 ID                            |
| text          | string   |  ✅ | 断言文本（可被审计）                       |
| claim_type    | string   |  ✅ | fact / judgment / recommendation |
| confidence    | number   |  ✅ | 0~1 置信度（用于 gate 与升级策略）           |
| scope         | string   |  ✅ | 断言适用边界（范围/条件）                    |
| audience      | string   |  ⭕ | 受众（外发/内部）                        |
| evidence_refs | string[] |  ✅ | 支撑该断言的 EvidenceRef 列表            |
| created_by    | object   |  ✅ | 生成来源（run_id/step_id/model）       |

##### EvidenceRef（证据回指）

| 字段             | 类型            | 必填 | 解释                                             |
| -------------- | ------------- | -: | ---------------------------------------------- |
| evidence_id    | string        |  ✅ | 证据 ID                                          |
| artifact_id    | string        |  ✅ | 指向证据所在工件                                       |
| locator        | object        |  ✅ | 定位信息（页码/行号/段落/时间戳等）                            |
| locator.kind   | string        |  ✅ | page / line / section / timestamp / url（若来源允许） |
| locator.start  | string/number |  ✅ | 起点                                             |
| locator.end    | string/number |  ⭕ | 终点                                             |
| snippet_digest | string        |  ⭕ | 证据摘录的 hash/摘要（避免泄露全文也可校验一致性）                   |
| source_type    | string        |  ✅ | provided / kb / web（需与 sources.scope 一致）       |
| retrieved_at   | string        |  ✅ | 获取时间                                           |

**最小示例（JSON）**

```json
{
  "claim": {
    "claim_id": "cl_001",
    "text": "建议优先采用方案A，原因是对现有流程改动最小且风险可控。",
    "claim_type": "recommendation",
    "confidence": 0.72,
    "scope": "在当前约束不变且证据门槛=high的前提下",
    "audience": "external",
    "evidence_refs": ["ev_01"],
    "created_by": { "run_id": "run_12ab", "step_id": "step_03_internal_draft", "model": "pro_model_x" }
  },
  "evidence": {
    "evidence_id": "ev_01",
    "artifact_id": "sha256:a1b2...c3d4",
    "locator": { "kind": "section", "start": "3.2", "end": "3.4" },
    "snippet_digest": "sha256:77aa...11ff",
    "source_type": "provided",
    "retrieved_at": "2026-02-27T10:16:40Z"
  }
}
```

---

#### 2.4.5 PolicyDecision / GateResult（门禁决策与证据）

##### PolicyDecision（门禁决策）

| 字段               | 类型       | 必填 | 解释                                                       |
| ---------------- | -------- | -: | -------------------------------------------------------- |
| decision_id      | string   |  ✅ | 决策 ID                                                    |
| gate_name        | string   |  ✅ | 门禁名（structure / claim_evidence / security / publish / …） |
| decision         | string   |  ✅ | allow / warn / block / needs_human                       |
| reasons          | string[] |  ✅ | 原因列表（可直接用于提示用户补齐）                                        |
| evidence_refs    | string[] |  ⭕ | 用于支撑门禁判断的证据回指（例如发现“外发稿出现英文缩写”的定位证据）                      |
| required_actions | string[] |  ⭕ | 需要执行的动作（例如“生成替换块并重跑 gate”）                               |
| policy_version   | string   |  ✅ | 门禁规则版本                                                   |
| created_at       | string   |  ✅ | 时间                                                       |

##### GateResult（门禁结果，面向运行记录）

| 字段             | 类型      | 必填 | 解释                                      |
| -------------- | ------- | -: | --------------------------------------- |
| gate_result_id | string  |  ✅ | gate 结果 ID                              |
| run_id         | string  |  ✅ | run                                     |
| step_id        | string  |  ⭕ | 绑定步骤（若为全局 gate 可为空）                     |
| decision_id    | string  |  ✅ | 指向 PolicyDecision                       |
| status         | string  |  ✅ | passed / warned / blocked / needs_human |
| fail_closed    | boolean |  ✅ | 是否 fail-closed（高风险动作必须 true）            |

**最小示例（JSON）**

```json
{
  "policy_decision": {
    "decision_id": "pd_33aa",
    "gate_name": "external_style",
    "decision": "block",
    "reasons": ["外发稿出现英文缩写，违反外发全中文约束", "外发稿出现内部痕迹字段"],
    "evidence_refs": ["ev_21"],
    "required_actions": ["生成可直接粘贴的替换段落", "替换后重新运行 external_style gate"],
    "policy_version": "v1.0",
    "created_at": "2026-02-27T10:28:10Z"
  },
  "gate_result": {
    "gate_result_id": "gate_7c91",
    "run_id": "run_12ab",
    "step_id": "step_04_external_draft",
    "decision_id": "pd_33aa",
    "status": "blocked",
    "fail_closed": true
  }
}
```

---

#### 2.4.6 RunRecord（一次运行的全链路记录）

| 字段                  | 类型           | 必填 | 解释                                                  |
| ------------------- | ------------ | -: | --------------------------------------------------- |
| run_id              | string       |  ✅ | 运行 ID                                               |
| task_id             | string       |  ✅ | 关联 TaskSpec.task_id                                 |
| pipeline_id         | string       |  ✅ | 运行的 pipeline                                        |
| status              | string       |  ✅ | queued/running/completed/failed/needs_human/aborted |
| started_at          | string       |  ✅ | 开始                                                  |
| ended_at            | string       |  ⭕ | 结束                                                  |
| steps               | StepResult[] |  ✅ | 全部步骤结果                                              |
| artifacts           | string[]     |  ✅ | 产物列表（artifact_id）                                   |
| gates               | string[]     |  ✅ | gate_result_id 列表                                   |
| metrics             | object       |  ✅ | 总体成本（token/toolCalls/elapsed）                       |
| human_interventions | object[]     |  ⭕ | 人工介入记录（审批/补材料/确认路由）                                 |
| final_outputs       | object       |  ✅ | 对外/对内的最终入口工件（artifact_id）                           |

**最小示例（JSON）**

```json
{
  "run_id": "run_12ab",
  "task_id": "task_8f3c1d2a",
  "pipeline_id": "report_pipeline_v1",
  "status": "completed",
  "started_at": "2026-02-27T10:16:00Z",
  "ended_at": "2026-02-27T10:35:20Z",
  "steps": [
    { "step_id": "step_01_purpose", "status": "succeeded", "started_at": "2026-02-27T10:16:00Z", "ended_at": "2026-02-27T10:16:08Z", "attempts": 1, "artifacts_out": ["sha256:111..."], "claims_out": [], "gate_results": ["gate_a1"], "metrics": { "tool_calls": 0, "token_used": 1200, "elapsed_ms": 8000 } }
  ],
  "artifacts": ["sha256:111...", "sha256:222...", "sha256:333..."],
  "gates": ["gate_a1", "gate_b2", "gate_c3"],
  "metrics": { "tool_calls": 18, "token_used": 68000, "elapsed_ms": 1160000 },
  "final_outputs": {
    "internal_draft": "sha256:222...",
    "external_draft": "sha256:333...",
    "publish_manifest": "sha256:444..."
  }
}
```

---

#### 2.4.7 EvoMapSignal（从 AIOS 侧如何派生并对接 EvoMap）

> 该契约需与 `OPENCLAW_EVOMAP_TYPES_20260226.ts` 的 `EvomapSignal` 对齐，保证桥接成本最低。

| 字段          | 类型     | 必填 | 解释                                                      |
| ----------- | ------ | -: | ------------------------------------------------------- |
| id          | string |  ✅ | signal id                                               |
| fingerprint | string |  ✅ | 去重指纹（同类问题聚合）                                            |
| source      | string |  ✅ | agent-events / diagnostic-events / manual（见类型定义）        |
| severity    | string |  ✅ | low / medium / high                                     |
| kind        | string |  ✅ | 信号类型（例如 gate.blocked / tool.cooldown / budget.exceeded） |
| text        | string |  ✅ | 人可读描述（用于审批/复盘）                                          |
| ts          | number |  ✅ | 时间戳（ms）                                                 |
| session_key | string |  ⭕ | 会话/租户键（若适用）                                             |
| run_id      | string |  ⭕ | 关联 run                                                  |
| metadata    | object |  ⭕ | 结构化信息（gate_name、error_category、model、tool、counts 等）     |

**最小示例（JSON）**

```json
{
  "id": "sig_01",
  "fingerprint": "fp_gate_claim_evidence_report_pipeline_v1",
  "source": "diagnostic-events",
  "severity": "high",
  "kind": "gate.blocked",
  "text": "claim-evidence 门禁连续失败：关键结论缺少证据回指或证据门槛不足",
  "ts": 1772198400123,
  "session_key": "tenant_default",
  "run_id": "run_12ab",
  "metadata": {
    "gate_name": "claim_evidence",
    "pipeline_id": "report_pipeline_v1",
    "recent_failures": 3,
    "policy_profile": "strict_external"
  }
}
```

---

### 2.5 端到端业务流（必须画出文字版时序）

> 下面用“文字版时序 + 输入/产物/门禁/失败处理”给出 4 条必须覆盖的端到端流程。

---

#### 2.5.1 写报告端到端自动化（目的识别→证据装载→底稿→外发→复审→脱敏→发布）

**参与者**

* 用户（User）
* AIOS 入口（Task Intake）
* Router（路由器）
* PipelineRunner（执行器）
* MemoryManager（证据/记忆门面）
* ChatgptRESTConnector（多模型服务连接器）
* PolicyGate（门禁）
* RedactConnector（脱敏连接器）
* PublishConnector（发布连接器）
* EventLog/ArtifactStore（落盘）
* EvoMapBridge（信号派生）

**时序（文字版）**

1. User → Task Intake：提交“一句话需求” +（可选）REPORT_SPEC.yaml
2. Task Intake → TaskSpecService：生成 TaskSpec（raw_query 永不丢失，补齐 scope/distribution/evidence/budget/risk）
3. TaskSpecService → EventLog：写 `task.created`
4. Task Intake → Router：基于 TaskSpec.intent=report 选择 `report_pipeline`
5. Router → PolicyGate（route_gate）：校验外发任务必须具备 distribution/external、sources.scope 明确、risk_level/budget 合规
6. PipelineRunner → Step(purpose_identify)：

   * 输入：TaskSpec.raw_query +（可选）REPORT_SPEC.yaml 摘要
   * 输出：PurposeDecision artifact（包含目的类型、推荐模块组合，来自 `REPORT_PURPOSE_MATRIX_20260208.md` 的固化映射）
7. PolicyGate（purpose_gate）：若目的不确定/多解 → needs_human（停在“澄清问题”）
8. PipelineRunner → Step(evidence_load)：

   * 调用 MemoryManager → 证据包生成（EvidencePack artifact）
9. PolicyGate（evidence_gate）：

   * evidence.level=high 时：证据不足 → block（fail-closed），输出待补材料清单 artifact
   * evidence.level=medium/low：允许降级但必须在底稿“假设与待确认”中显式声明
10. PipelineRunner → Step(internal_draft_generate)：

* 调用 ChatgptRESTConnector（或其他模型通道）生成“内部底稿”（结构要求来自 `REPORT_TRIPLEKIT_PROMPTS_20260208.md`）
* 同步提取 Claim/EvidenceRef（每条关键结论必须可回指证据）

11. PolicyGate（internal_structure_gate + claim_evidence_gate）：

* 缺章节/缺材料索引/关键结论无证据 → quality_block
* 处理：允许 1 次“自修复”步骤（生成替换块并重写相关段落）

12. PipelineRunner → Step(external_draft_generate)：

* 基于内部底稿的“关键结论/建议/需要支持/近期安排”生成外发沟通稿（严格遵守外发约束）

13. PolicyGate（external_style_gate + no_internal_trace_gate）：

* 出现英文/缩写/内部痕迹/证据链细节 → block（fail-closed）

14. PipelineRunner → Step(pro_review)：

* 调用复审提示词（`REPORT_TRIPLEKIT_PROMPTS_20260208.md`）生成：结论三选一 + 必须修改（含替换块）+ 建议优化 + 追问清单

15. PolicyGate（audit_gate）：

* 若结论=可以外发 → pass
* 若=建议修改后外发 → 应用替换块（patch_apply step），回到 external_style_gate 再验
* 若=暂不建议外发 → needs_human（输出缺口与追问）

16. PipelineRunner → Step(redact)：脱敏处理（外发稿/附件）产出 redacted_external_draft artifact
17. PolicyGate（security_gate）：脱敏结果校验（敏感信息策略）
18. PipelineRunner → Step(publish)：发布，产出 publish_manifest artifact（含发布元信息、引用的最终工件）
19. PipelineRunner → RunRecordBuilder：生成 RunRecord，写 `run.completed`
20. EvoMapBridge：从 gate.blocked/重试/预算超限等派生 signals → 进入自进化闭环

**关键输入**

* raw_query（用户一句话需求）
* REPORT_SPEC.yaml（若采用 spec 驱动，见 `REPORT_SPEC_20260202.md`）
* sources.scope / evidence.level / distribution

**关键中间产物（artifacts）**

* PurposeDecision（目的识别结果）
* EvidencePack（证据包）
* InternalDraft（内部底稿）
* ExternalDraft（外发沟通稿）
* ReviewPatch（复审替换块）
* RedactedExternalDraft（脱敏外发稿）
* PublishManifest（发布清单）
* RunRecord（全链路记录）

**质量门禁点（Gate）**

* route_gate（入口约束）
* evidence_gate（证据门槛）
* internal_structure_gate（底稿结构）
* claim_evidence_gate（断言-证据）
* external_style_gate（外发全中文/无内部痕迹）
* audit_gate（复审结论）
* security_gate（脱敏）
* publish_gate（发布审批/预算）

**失败后的降级/重试/人工介入点**

* 证据不足：输出“待补材料清单”，needs_human
* 模型输出不合规：自动生成替换块进行 1 次修复；仍失败→needs_human
* 发布：高风险动作默认需要审批；审批未通过→run.aborted（保留所有 artifacts）

---

#### 2.5.2 做调研端到端自动化（含必要时的“辩论/交叉验证”）

**参与者**

* 用户
* AIOS（Task Intake/Router/PipelineRunner）
* MemoryManager（检索与证据包）
* WebResearchConnector（可选：仅当 sources.scope=web-ok-with-citations）
* MultiModelRunner（辩论/交叉验证）
* PolicyGate
* ArtifactStore/EventLog

**时序（文字版）**

1. User → Task Intake：提交调研问题（明确 scope 与 evidence.level）
2. Router：选择 `research_pipeline`
3. Step(scope_define)：生成“调研范围与问题树”artifact（包含：要回答什么/不回答什么/需要哪些材料）
4. PolicyGate（scope_gate）：若范围过大或缺关键前置 → needs_human（追问清单）
5. Step(kb_pre_retrieve)：MemoryManager 检索并生成 evidence_pack_0 artifact
6. PolicyGate（evidence_gate）：评估证据覆盖度；不足则：

   * 若 sources.scope=provided-only：输出“缺口材料清单”，停止
   * 若 sources.scope=web-ok-with-citations：进入 web_research
7. Step(web_research，可选)：抓取/整理外部证据为 artifacts，并生成 EvidenceRef（必须可引用）
8. Step(analysis_synthesis)：基于证据包生成初版分析与 claims
9. PolicyGate（trigger_debate_gate）：满足触发条件则强制进入辩论/交叉验证（见 2.7）
10. Step(debate_rounds)：多模型并行生成 claim_set_A/B → diff → arbitration → 输出 DebateResult（冲突清单、替换块、风险条款）
11. PolicyGate（claim_evidence_gate + consistency_gate）：

    * 冲突未解决：必须在最终稿“假设与待确认/风险与不确定性”中显式呈现，或 needs_human 决策
12. Step(draft_outputs)：按“内部底稿/外发沟通稿（可选）”生成产物
13. Step(ingest_to_kb，可选)：若需要入库，走 write_gate（默认审批）
14. RunRecordBuilder：落盘全链路记录并产出可回放入口

**关键输入**

* 调研问题 + sources.scope + evidence.level + distribution
* （可选）REPORT_SPEC.yaml（当调研产出也采用 spec 驱动）

**关键中间产物**

* ResearchScope（范围定义）
* EvidencePack_0 / WebEvidencePack
* ClaimSet_A / ClaimSet_B / ClaimDiff
* DebateResult（冲突清单、替换块、风险条款）
* InternalDraft / ExternalSummary（按需）
* RunRecord

**质量门禁点**

* scope_gate（范围可收敛）
* evidence_gate（证据门槛）
* trigger_debate_gate（强制多模型触发）
* claim_evidence_gate（断言-证据）
* consistency_gate（跨模型一致性）
* write_gate（入库审批）

**失败处理**

* 外部证据不可用：降级为“仅基于已有材料”的结论，并在产物中明确边界
* 辩论成本超预算：降级为“单模型 + 审计模式 + 风险条款”，并输出“需人工确认点”

---

#### 2.5.3 需求漏斗闭环（碎片→分类→立项→分派→执行→交付）

**参与者**

* 用户（碎片输入）
* FunnelApp（漏斗应用）
* Router/Scheduler/PipelineRunner（平台）
* PolicyGate
* ArtifactStore/EventLog

**时序（文字版）**

1. User → FunnelApp：提交碎片（想法/需求/问题/待办）
2. FunnelApp → ArtifactStore：保存 Fragment artifact（原始文本、来源、时间）
3. Step(classify_fragment)：生成分类结果 artifact（类别、优先级 P0/P1/P2、建议下一步）
4. PolicyGate（dup_gate）：去重（按 fingerprint），重复则合并并更新引用关系
5. Step(project_propose)：将碎片聚合成“立项建议”artifact（目标、范围、验收、风险）
6. PolicyGate（initiation_gate）：高风险/高成本立项→needs_human（审批）
7. Step(dispatch_tasks)：拆成可执行 TaskSpec（可能路由到 report/research/engineering 等 pipeline）
8. Scheduler：入队执行
9. Step(delivery_collect)：收集交付物 artifacts，生成 DeliveryManifest artifact
10. PolicyGate（delivery_gate）：验收是否满足“可点验/可回放”
11. RunRecordBuilder：把整个漏斗链路（从 fragment 到交付）串成可追溯的 ArtifactGraph

**关键输入**

* Fragment（碎片原文）
* 用户的优先级偏好（如有）
* 风险与预算（若涉及对外/写入/执行）

**关键中间产物**

* Fragment artifact
* Classification artifact
* ProjectProposal artifact
* TaskSpec 列表
* DeliveryManifest
* RunRecord/ArtifactGraph

**质量门禁点**

* dup_gate（去重合并）
* initiation_gate（立项审批）
* dispatch_gate（拆分合理性：每个 TaskSpec 可执行、可验收）
* delivery_gate（交付可点验/可回放）

**失败处理**

* 分类不确定：输出 3-5 个澄清问题，needs_human
* 立项未审批：保持候选状态，进入待办队列，不自动执行

---

#### 2.5.4 自进化闭环（Signal→Plan→Approval→Execute→Quarantine/Rollback→Promote）

**参与者**

* AIOS EventLog/RunRecord（事实与视图）
* SignalDeriver（信号派生器，属于 EvoMapBridge）
* EvoMapConnector（桥接）
* 审批者（人）
* Executor（执行器：dispatch_task/send_followup/rollback/pause）
* QuarantineManager（隔离器）
* PolicyGate（预算/审批/安全）

**时序（文字版）**

1. EventLog：持续追加 run/step/gate/tool/budget 等事件
2. SignalDeriver（周期任务或事件触发）：

   * 读取新事件 → 生成 `EvoMapSignal`（去重/分级/风暴抑制）→ signal artifact 落盘
3. EvoMapConnector.publish：把 signals 推送给 EvoMap（或批量）
4. EvoMap 侧生成 `EvomapEvolutionPlan`（计划）与 `EvomapRun`（运行），可能标记 requiresApproval（见 `OPENCLAW_EVOMAP_TYPES_20260226.ts`）
5. AIOS → EvoMapConnector.fetch：拉取待执行 plan
6. PolicyGate（approval_gate）：

   * requiresApproval=true 或 risk_level=high → 生成 ApprovalRequest artifact 并进入待审
7. 人工审批：批准/拒绝（写入 ApprovalRecord artifact）
8. Executor 执行 actions：

   * dispatch_task：派发一个“修复/改进”TaskSpec（例如改 gate 规则、补模板、加证据检查）
   * send_followup：发起追问/补材料请求
   * rollback：回滚某个 capsule/配置变更
   * pause：暂停某类 pipeline 或某 fingerprint 的自动执行
9. PolicyGate（budget_gate）：执行过程按 budget 约束（maxRunSeconds/maxToolCalls/maxTokens）
10. 失败处理：

* 若同 fingerprint 连续失败 → QuarantineManager 隔离（设置 quarantine_until_ts）
* 必要时生成 rollback plan（可能需要审批）

11. 成功处理：

* 达到质量/成功率提升阈值 → Promote（晋级 capsule），记录 `capsule.promoted`

12. 全过程回写：

* 将 plan/run/events/approvals/capsules 作为 artifacts 保存，并在 RunRecord 中形成“进化链路视图”

**关键输入**

* EventLog 中的 gate 结果、失败分类、预算超限、人工介入记录等
* EvoMap 的计划与审批结果

**关键中间产物**

* EvoMapSignal artifacts（含聚合统计）
* EvomapEvolutionPlan / EvomapRun / EvomapRunEvent / ApprovalRecord / Capsule artifacts
* Quarantine record / Rollback record

**质量门禁点**

* signal_gate（信号去重与风暴抑制）
* approval_gate（需要审批的动作不执行）
* budget_gate（预算护栏）
* quarantine_gate（隔离状态禁止自动执行）
* promote_gate（晋级条件）

**失败处理**

* EvoMap 不可用：signals 只落盘并进入“待同步队列”
* 执行失败：进入 quarantine + 生成 rollback 计划 + 输出“必须人工介入点”

---

### 2.6 EvoMap 纳入方案（必须可执行）

#### 2.6.1 选择：优先“桥接 openclaw 的 EvoMap”，AIOS 内不复刻全套闭环

**建议：桥接 openclaw 的 EvoMap（主路径）**，同时在 AIOS 保留“最小降级闭环（本地 signals + 人工计划）”以防 EvoMap 不可用。

**理由（对应 `AIOS_PLATFORM_INFRA_DESIGN_V0_20260227.md` 与 `OPENCLAW_EVOMAP_TYPES_20260226.ts`）**

1. **已有成熟机制与类型契约**：signals/plan/approval/budget/quarantine/capsule/run events 已定义，桥接能最快形成可运行闭环。
2. **避免在 AIOS 内重复造“进化系统”**：AIOS 的核心价值是把方法论固化为管线与门禁；EvoMap 属于“进化编排器”，适合做外部可替换组件。
3. **迁移/替换成本可控**：只要 AIOS 输出的 EvoMapSignal 与 `EvomapSignal` 对齐，并实现 `EvomapHubConnector` 的 hello/fetch/publish/report，未来可替换后端实现。

#### 2.6.2 迁移策略（分期）

* **阶段 1（最小可用）**：AIOS 只做三件事

  1. 从 EventLog/RunRecord 派生 `EvoMapSignal` 并落盘（含去重/分级/风暴抑制）
  2. 通过 EvoMapConnector.publish 推送 signals
  3. 通过 EvoMapConnector.fetch 拉取 plan，若 requiresApproval 则进入待审队列（不自动执行）
* **阶段 2（可控执行）**：加入 Executor，支持 `dispatch_task` 与 `send_followup`（低风险动作优先）；`rollback/pause` 必须审批。
* **阶段 3（治理与晋级）**：接入 capsule 晋级/回滚、隔离统计、命中率/误修率指标（对应 `EvomapMetrics`），形成“自进化看板”（report 接口）。

---

#### 2.6.3 AIOS 侧要产出哪些 signals、如何去重、如何分级、如何避免信号风暴、如何触发审批

> 目标：把“质量问题与返工成本”收敛为可观测、可验证、可迭代闭环（`AIOS_PLATFORM_INFRA_DESIGN_V0_20260227.md`）。

##### (1) 信号来源与 kind（建议最小集合）

* **gate.blocked**：任何门禁 blocked（尤其 external_style、claim_evidence、security、publish）
* **gate.warned_rate_high**：某门禁在窗口期内 warn 占比过高（提示规则过严/模板不稳）
* **retry.exhausted**：重试耗尽（外部系统不稳/策略不对）
* **budget.exceeded**：预算超限（对应 `guardrail.budget_exceeded` 的 run event 语义）
* **tool.cooldown**：稀缺资源（浏览器/发布通道）被冷却或长期排队
* **evidence.insufficient**：证据门槛不足导致任务无法推进（与 `REPORT_SPEC_20260202.md` 的 evidence.level 强相关）
* **consistency.conflict**：多模型/多来源冲突未解决（触发需要人工确认）
* **publish.blocked**：发布/写入副作用被审批拒绝或策略阻断

##### (2) 去重 fingerprint（指纹）策略（可执行）

fingerprint 必须稳定、可聚合，建议由以下要素拼接后做 hash：

* `pipeline_id`
* `step_id` 或 `gate_name`
* `kind`
* `error_category`（transient/permanent/policy/quality）
* `model_vendor_or_channel`（若与模型相关）
* `tool_name`（若与外部 connector 相关）
* `policy_profile`（strict_external 等）

示例（概念表达）：
`fingerprint = hash(pipeline_id + gate_name + kind + error_category + policy_profile)`

##### (3) 分级 severity（严重度）规则（可执行）

* **high**：

  * 外发相关 gate.blocked（external_style/security/publish）
  * claim_evidence blocked 且连续 N 次（例如 N=3）
  * budget.exceeded 导致 run aborted
  * 同 fingerprint 在隔离窗口内连续失败（关联 `EvomapSignalFailureTracker.recentFailures`）
* **medium**：

  * retry.exhausted 但可降级完成（例如缺证据但允许“明确边界”的内部稿）
  * consistency.conflict 需要人工确认
* **low**：

  * 单次 transient 失败且后续成功
  * warn 占比轻微上升

##### (4) 避免信号风暴（storm control）机制

* **窗口聚合**：以 `OPENCLAW_EVOMAP_TYPES_20260226.ts` 的 `EVOMAP_QUARANTINE_WINDOW_MS`（隔离观察窗口）为参照，signals 先聚合再上报：

  * 对同 fingerprint：窗口内最多上报 1 条“聚合信号”，metadata 记录 counts/last_ts/recent_failures。
* **速率限制**：每 fingerprint 每 X 分钟最多 1 条；超过则只更新本地计数，不发新 signal。
* **阈值升级**：low → medium → high 仅在累计失败次数/连续失败次数达到阈值时升级，避免短抖动触发高风险进化。
* **压缩上报**：把同类 signals 打包成“signal_batch artifact”，只推送 batch 引用与摘要。

##### (5) 触发审批（requiresApproval）建议规则

对齐 `EvomapEvolutionPlan.requiresApproval` 与 `riskLevel`（见类型定义）：

* 以下任何一条命中 → requiresApproval=true：

  1. action.type 为 `rollback` 或 `pause`
  2. action 会产生对外副作用（发布、对外发送、写入知识库/记忆、执行命令、覆盖配置）
  3. risk_level=high 或 context.distribution=external 且 evidence.level=high（高标准+高风险）
  4. vendor fingerprint 不匹配（见下节）
  5. budget 超过默认预算或超出策略阈值

---

#### 2.6.4 守护条件：预算、审批、隔离、回滚、vendor fingerprint

> 这些守护条件必须“系统强制”，不能靠提示词。

1. **预算（budget guardrail）**

* 直接采用 `OPENCLAW_EVOMAP_TYPES_20260226.ts` 的 `EvomapGuardrailBudget` 结构：`maxRunSeconds/maxToolCalls/maxTokens`。
* 在 AIOS 侧：每个 run/step 都要记录 metrics；一旦超过预算：

  * 立即触发 `guardrail.budget_exceeded` 语义（作为事件与信号）
  * 对高风险动作 fail-closed（停止执行、进入待审）

2. **审批（approval）**

* 审批必须落盘为 artifact（ApprovalRecord），并写 EventLog（approved/denied）。
* 默认策略（建议）：

  * external 发布、写入记忆、rollback/pause、任何执行命令类动作 → 必须审批
  * 纯分析/只读检索 → 可自动执行

3. **隔离（quarantine）**

* 对齐 `EVOMAP_QUARANTINE_DURATION_MS`：同 fingerprint 连续失败达到阈值 → 隔离 24 小时（或按策略）。
* 隔离期间：

  * Router/Scheduler 对匹配 fingerprint 的任务直接降级为 needs_human 或切换到安全模式（例如只生成“待确认清单”而不发布）。

4. **回滚（rollback）**

* rollback 作为 EvoMap action（`EvomapPlanActionType="rollback"`）执行前必须满足：

  * 有可回滚对象（capsule/config 版本）与明确影响范围（run_id/pipeline_id）
  * 有回滚后验证 gate（确保不引入更大损害）
* rollback 执行后必须生成：RollbackReport artifact（前后对比、影响、再发风险）

5. **vendor fingerprint（供应方指纹）**

* 对齐 `EVOMAP_CANONICAL_VENDOR_SOURCE`：AIOS 执行进化动作时必须记录 `vendor_source`，并在 PolicyGate 校验：

  * 非预期来源（例如未知 evolver）→ requiresApproval=true 或直接 block
* 目的：防止“非预期版本/非预期执行器”做高风险动作。

---

### 2.7 多模型机制（辩论/仲裁/交叉验证）

#### 2.7.1 触发条件（何时必须双模型/多模型）

满足任一条件即触发（可配置为 gate）：

1. `context.distribution=external` 且 `risk_level` 为 medium/high（对外高风险）
2. `evidence.level=high` 且出现以下任一情况：

   * claim_evidence_gate 被 block 或 warn 次数超过阈值
   * 同一关键结论存在冲突证据（EvidenceRef 指向不同来源且结论相反）
3. `sources.scope=web-ok-with-citations`（外部来源易冲突）且需要形成可外发结论
4. 任务属于“决策/请示/合作评估”等目的（来自目的矩阵的高敏感场景）
5. 任何自动发布/写入动作之前的最终审计（audit_gate）可以要求双模型

> 关键：触发条件必须落在 PolicyGate 配置中，成为**可执行规则**，而不是“建议做一下”。

#### 2.7.2 输入输出：每轮 debate 的产物是什么

把多模型机制定义为一个可运行的子流程（子 pipeline 或 step group），最小产物如下（全部落为 artifacts）：

**输入（DebateSpec）**

* `topic`（要辩论的问题/断言集合）
* `evidence_pack_ref`（证据包 artifact_id）
* `claims_to_verify[]`（需要验证的 claim_id 或候选断言）
* `roles`：proposer（主张者）/ skeptic（质疑者）/ arbiter（仲裁者）
* `rounds`（轮次，建议 1-2）
* `budget`（预算护栏）
* `output_requirements`（例如必须给替换块、必须给风险条款）

**输出（DebateResult）**

* `claim_set_A`（模型 A 断言集合，含 evidence_refs）
* `claim_set_B`（模型 B 断言集合，含 evidence_refs）
* `claim_diff`（Claim diff：一致/冲突/缺证据/不同边界）
* `conflict_list`（冲突清单：每条冲突的原因、需要补哪些证据/该如何表述边界）
* `replacement_blocks`（替换块：可直接粘贴到目标稿件的段落/表格）
* `risk_clauses`（风险条款：对外稳健表达的“条件/假设/待确认”）
* `cost_report`（成本与耗时：token/toolCalls/elapsed）

这些产物将作为 Gate 的 Evidence：audit_gate、claim_evidence_gate、consistency_gate 的决策依据。

#### 2.7.3 成本控制：token/时间/并发/冷却与降级策略

**成本控制（硬机制）**

* token：DebateSpec 内显式 `max_tokens`；超出即中止并输出 cost_report+partial artifacts
* 时间：每轮 debate 设置 `timeout_seconds`；超时视为 failed（可触发降级）
* 并发：MultiModelRunner 的并行数受 ResourceManager 约束（避免与发布/浏览器资源冲突）
* 冷却：同 fingerprint 的 debate 在短窗口内不重复触发（避免风暴），仅更新统计

**降级策略（可运行）**

* 降级 1：从“三模型（A/B/仲裁）”降为“双模型（A/B）+ 规则仲裁”（只做 diff 与冲突清单，不做第三模型）
* 降级 2：从“双模型”降为“单模型 + 审计模式输出”（强制输出：待确认清单、风险条款、不可外发提示）
* 降级 3：直接 needs_human（当预算不足且风险高，例如 external+high）

---

### 2.8 可执行路线图（必须给里程碑 + 验收标准）

> 按 `AIOS_REQUIREMENTS_FULLVIEW_V5_20260227.md` 的特别要求：先把“写报告端到端自动化”做到可稳定运行，再扩展到其他场景。这里给 M0-M5 分期。

---

#### M0：契约冻结 + 最小可运行平台骨架

**交付物（可点验）**

* 关键契约 v1：TaskSpec/StepSpec/StepResult/Artifact/Claim/EvidenceRef/GateResult/RunRecord/EvoMapSignal（与本答复 2.4 对齐）
* SchemaRegistry + 校验器（运行时强制校验）
* EventLog（append-only）+ ArtifactStore（sha256 内容寻址）对外 API 稳定
* RunRecordBuilder（至少能从事件构建最小 RunRecord）
* PipelineRegistry/Router/Scheduler/PipelineRunner 的最小闭环（可跑通一条 demo pipeline）

**验收标准（可量化/可回放）**

* 给定同一输入 TaskSpec：重复运行不产生重复副作用（idempotency 生效）
* 任一 run：能回放出（1）任务输入（2）每步产物（3）每个 gate 决策（4）成本统计
* 任一 artifact：可用 sha256 校验内容一致性；引用关系可重建

**风险与对策**

* 风险：契约不稳导致上层应用频繁返工

  * 对策：M0 明确“v1 冻结范围”（仅覆盖报告/调研/漏斗/进化必需字段），后续扩展走版本化（v1→v1.1）

---

#### M1：写报告端到端自动化 MVP（稳定运行，先不追求完美）

**交付物**

* report_pipeline_v1：purpose_identify → evidence_load → internal_draft → external_draft → pro_review → redact → publish（可配置 dry-run）
* PurposeMatrixRegistry（把 `REPORT_PURPOSE_MATRIX_20260208.md` 固化为可机读规则表）
* ReportSpec 支持：读取/校验 REPORT_SPEC.yaml 关键字段（scope/distribution/evidence/detail_level）
* 核心门禁：evidence_gate、internal_structure_gate、claim_evidence_gate、external_style_gate、audit_gate、security_gate、publish_gate
* 产物标准化：内部底稿/外发稿/替换块/发布清单/RunRecord 全部落盘为 artifacts

**验收标准**

* 在“provided-only + external + evidence=high”的配置下：

  * 若证据不足，系统必须 fail-closed 并输出“待补材料清单”（不可生成可外发稿）
  * 若证据足够，系统一次运行产出：internal_draft、external_draft、review_patch、publish_manifest、run_record
* external_style_gate：对外稿必须“全中文、无内部痕迹”，一旦发现违反必须 block（可用自动检测规则 + 证据定位）
* audit_gate 输出必须满足 `REPORT_TRIPLEKIT_PROMPTS_20260208.md`：结论三选一 + 必须修改（含替换块）

**风险与对策**

* 风险：模型输出不稳定导致外发稿频繁被 gate block

  * 对策：把 block 的原因结构化为 signals，进入 EvoMap；同时提供“自修复一次”的 patch_apply 流程，减少人工改稿

---

#### M2：可回放与治理增强（幂等持久化、缓存治理、资源与成本看板）

**交付物**

* IdempotencyStore 持久化（避免进程内无界增长的问题，见 `AIOS_PLATFORM_INFRA_DESIGN_V0_20260227.md`）
* Checkpoint/恢复：长任务中断可恢复
* ArtifactGraphView：可视化/可查询的产物依赖与证据回指
* 资源治理：浏览器互斥、FIFO、冷却策略（ResourceManager）
* 成本与质量指标派生：从事件派生 dashboard 级数据（无需业务模块耦合）

**验收标准**

* 进程异常退出后：同一 run 可恢复或可明确标记为 aborted，并保留全部中间产物与原因
* 幂等缓存不会无界增长，且命中率可统计
* 能对任一报告 run 回放出“证据→结论→外发稿→替换块→发布”的链路

**风险与对策**

* 风险：治理增强拖慢交付速度

  * 对策：M2 只做“影响稳定性与可回放”的治理；其他优化后置

---

#### M3：调研端到端自动化 + 多模型机制工程化

**交付物**

* research_pipeline_v1：scope_define → retrieve →（可选 web_research）→ analysis → debate（按 gate 触发）→ outputs →（可选入库）
* MultiModelRunner/DebateOrchestrator：标准产物（claim_set/diff/conflict/replacement/risk/cost）
* consistency_gate：跨模型一致性审计与风险条款强制输出

**验收标准**

* 当触发条件命中：必须产生 DebateResult artifacts（不可跳过）
* 成本超预算时：必须按降级策略输出“冲突清单 + 待确认项 + 风险条款”，并标记 needs_human 或 warn
* 入库/写入类动作默认审批（fail-closed）

**风险与对策**

* 风险：多模型成本过高

  * 对策：默认 1 轮、严格预算、可配置触发条件；把 debate 用在“外发/高风险/高证据门槛”任务

---

#### M4：需求漏斗闭环（碎片→立项→分派→交付）

**交付物**

* intake_pipeline_v1：fragment_capture → classify → dedup → project_propose → approval(optional) → dispatch_tasks
* DeliveryManifest + ArtifactGraph 串联：从碎片到交付的可追溯链
* 与 report/research pipeline 打通：漏斗分派的 TaskSpec 直接走平台执行

**验收标准**

* 任一碎片：都能追溯到（分类结果→是否立项→产生了哪些 TaskSpec→最终交付 artifacts）
* 去重有效：同 fingerprint 的碎片不会无限膨胀
* 高风险立项必须审批（否则不执行）

**风险与对策**

* 风险：漏斗容易变成“堆列表”

  * 对策：验收以“闭环率”（从碎片到交付）与“可回放”作为硬指标，而不是条目数量

---

#### M5：EvoMap 全闭环（可控自进化）

**交付物**

* EvoMapBridge v1：signals 派生/聚合/上报、plan 拉取、approval、executor、quarantine、rollback、promote
* 与 `OPENCLAW_EVOMAP_TYPES_20260226.ts` 对齐的 connector 实现（hello/fetch/publish/report）
* 指标：EvomapMetrics（命中率/误修率/隔离率/回滚率等）与 AIOS 运行指标联动

**验收标准**

* 在连续失败场景下：系统能自动生成 signal → plan（needs_approval）→ 人工批准后执行 dispatch_task → 质量指标提升或触发隔离/回滚
* 隔离窗口/隔离时长生效（与常量语义一致），隔离期间不会重复触发危险动作
* 每次进化动作都有可回放证据链（signals→plan→approval→run events→capsule state）

**风险与对策**

* 风险：自进化误修带来系统性风险

  * 对策：默认 requiresApproval、预算护栏、隔离与回滚强制；先只允许低风险 action（dispatch_task/send_followup），高风险 action 必须审批

---

### 2.9 缺口清单与追问（用于下一轮迭代）

#### 2.9.1 当前材料里缺的关键信息（最多 10 条，按优先级）

1. **持久化边界与数据保留策略**：EventLog/ArtifactStore/索引/缓存的默认落点、备份与保留期（`AIOS_PLATFORM_INFRA_DESIGN_V0_20260227.md` 已提出但未定）。
2. **REPORT_SPEC.yaml 的生产与更新入口**：由谁生成/何时冻结/如何与 TaskSpec 对齐（`REPORT_SPEC_20260202.md` 描述流程，但缺“平台落地接口”）。
3. **发布/写入类副作用的审批策略细则**：哪些动作默认审批、哪些可自动、审批入口在哪里（`AIOS_PLATFORM_INFRA_DESIGN_V0_20260227.md` 提到守护条件但需落地规则表）。
4. **ChatgptREST 的调用契约细节**：AIOS 侧需要哪些字段（job_id、idempotency、cost、模型选择），以及是否所有模型调用都统一走该服务（`AIOS_PLATFORM_INFRA_DESIGN_V0_20260227.md` 提出定位问题）。
5. **安全标签与脱敏规则的分类体系**：security.label/tags 的枚举、哪些内容必须脱敏、外发禁用词规则的机器判定策略（`REPORT_TRIPLEKIT_PROMPTS_20260208.md` 给了约束，但需系统化规则）。
6. **PurposeMatrix 的机读化表示**：`REPORT_PURPOSE_MATRIX_20260208.md` 目前是文本矩阵，缺固化到 registry 的字段结构与版本策略。
7. **证据包的结构细则**：EvidencePack artifact 的内部结构（索引、摘要、定位）与 EvidenceRef.locator 的标准（页码/段落/行号的统一）。
8. **多模型策略的模型池与成本阈值**：哪些任务触发哪些模型组合、成本上限、并发限制。
9. **EvoMap 的租户/会话键策略**：`session_key`/tenant 如何分配，如何在多项目之间共享或隔离 signals/plans。
10. **人工介入的交互面**：needs_human 时如何呈现（命令行/前端/消息），如何把审批/补材料的结果回填到 TaskSpec/RunRecord。

#### 2.9.2 3-5 个最小澄清问题（你回答后我就能把方案从 v0 推进到 v1）

1. REPORT_SPEC.yaml 是否对“报告类任务”拥有**最高优先级**（覆盖 raw_query 的口头描述），并且是否允许“非报告任务”也复用 spec 机制？
2. AIOS 的 EventLog/ArtifactStore 默认要落在哪个“可持久化数据域”，以及保留期/备份策略的最低要求是什么？
3. ChatgptREST 在你的体系里是：

   * A) 仅用于 Pro 复审与长答，还是
   * B) 所有模型调用统一走它（便于归档与成本统计）？
4. 外发/写入/执行类动作的默认审批策略：哪些必须审批、哪些可自动（给一个最小规则表即可）？
5. EvoMap 接入希望从哪一步开始：先只做 signals+plan 拉取（不执行），还是可以从 dispatch_task 开始执行低风险动作？

#### 2.9.3 下一轮追问“提示词模板”（用于 follow-up）

> 你可以直接复制以下模板发我，我会按模板把方案推进到 v1（更贴近你的最终落地形态）。

**模板 1：契约落地（从草案到可实现）**

```text
基于 R1 的 2.4 契约草案，请把 TaskSpec/StepSpec/StepResult/Artifact/RunRecord 的字段定稿为 v1：
1) 给出字段的必填/可选、默认值、枚举、版本号策略
2) 给出至少 3 个端到端样例（写报告/做调研/需求漏斗），要求样例之间字段一致
3) 给出 GateResult 的规则表（哪些 gate 必跑、fail-closed 的范围）
只按文件名引用，不要出现路径/URL。
```

**模板 2：写报告流水线可执行化（把步骤变成可跑的 pipeline 定义）**

```text
基于 R1 的 report_pipeline_v1，请输出：
1) pipeline 的 steps 列表（每步 capability、输入artifact、输出artifact、retry_policy、gate_profile）
2) 每个 gate 的判定规则（至少 external_style、claim_evidence、evidence_gate、audit_gate、publish_gate）
3) 失败降级与人工介入点的状态机（queued/running/needs_human/failed/aborted）
只按文件名引用，不要出现路径/URL。
```

**模板 3：EvoMap 桥接细化（从“建议桥接”到“可上线的桥接协议”）**

```text
基于 R1 的 EvoMapBridge 方案，请输出：
1) AIOS -> EvoMap 的 signals 映射表（kind/severity/fingerprint 规则）
2) EvoMapPlanAction 在 AIOS 侧的执行白名单（先支持 dispatch_task/send_followup）
3) 审批与隔离/回滚的规则表（requiresApproval 的触发、预算默认值、隔离窗口/时长）
只按文件名引用，不要出现路径/URL。
```

**模板 4：多模型机制工程化（辩论/仲裁作为可运行子流程）**

```text
基于 R1 的多模型机制，请输出一个“debate 子流程”的可执行定义：
1) 触发条件 -> DebateSpec 生成规则
2) A/B/仲裁的输入输出 artifact 规范（claim_set/diff/conflict/replacement/risk/cost）
3) 成本控制与降级策略的规则表（预算不足/超时/并发限制）
只按文件名引用，不要出现路径/URL。
```

---

## 3. 评分与通过标准（你需要给结论）

* **结论：条件通过**
* **必须补齐的 3-7 条（及完成标准）**

  1. **持久化边界与保留策略定稿**：明确 EventLog/ArtifactStore/索引/缓存的默认落点与保留期；完成标准：写成一份可执行的“数据域与保留策略表”，并能在 RunRecord 中记录数据域版本。
  2. **审批策略规则表（最小版）**：列出发布/写入/回滚/暂停/执行命令等动作的默认审批要求；完成标准：PolicyGate 可根据规则表给出 allow/block/needs_human，且高风险动作 fail-closed。
  3. **REPORT_SPEC.yaml 与 TaskSpec 的对齐规则**：spec 字段如何覆盖/补齐 TaskSpec，冲突如何处理；完成标准：给出 3 个样例并能通过 schema 校验与路由。
  4. **PurposeMatrix 机读化与版本策略**：把 `REPORT_PURPOSE_MATRIX_20260208.md` 固化成 registry（字段结构+版本号）；完成标准：purpose_identify step 可稳定输出模块组合与理由，并可回放。
  5. **证据包结构与 EvidenceRef.locator 标准**：定义 evidence_pack artifact 内部结构与 locator 的统一规则；完成标准：claim_evidence_gate 能对关键结论做可定位的证据校验与失败回指。
  6. **ChatgptREST 调用契约选择与落地**：明确是否统一走 ChatgptREST 以及 AIOS 需要的最小字段集；完成标准：模型调用可归档、可回放、可统计成本，且不修改服务本体。
  7. **EvoMapBridge 的最小上线形态**：先实现 signals 聚合上报 + plan 拉取 + requiresApproval 待审；完成标准：能从一次 report_pipeline 的 gate.blocked 自动生成 signal，并在 EvoMap 侧形成 requiresApproval 的 plan（不执行也可），链路可回放。
