# ChatgptREST 问题知识系统与图检索架构草案

日期：2026-03-09  
范围：把 `issue ledger / incidents / jobs / artifacts / 历史文档 / GitNexus` 收敛成统一中间层，并为后续图检索、归档、自动收口提供稳定基线。  
结论：**先做数据审计与中间层，不先做 graph-first 实现。**

## 1. 目标

当前与“问题/修复/验证/演进”相关的数据分散在多处：

- 运行态：
  - `state/jobdb.sqlite3`
  - `artifacts/jobs/<job_id>/`
  - `artifacts/monitor/`
- 治理态：
  - `client_issues`
  - `incidents`
  - `client_issue_events`
- 文档态：
  - `docs/handoff_chatgptrest_history.md`
  - `docs/issues_registry.yaml`
  - `docs/dev_log/*.md`
- 代码图态：
  - GitNexus symbol / process / impact graph

问题不是“没有记录”，而是：

- 真相源分散，缺统一对象模型
- `open issue list` 和历史总结容易漂移
- `mitigated / closed` 缺可计算的统一口径
- 新客户端/新 Codex 很难快速知道“现在什么是已知问题、应该如何使用”

目标是建立一套统一体系，使系统可以同时支持：

- 当前 open issue 治理
- 历史问题追溯
- live 验证收口
- 客户端成功使用后的自动关闭
- 文本检索与图检索
- 新 agent 的快速 onboarding

## 2. 工作原则

### 2.1 不先建图，先建中间层

不能先挑图库或框架，然后倒推数据结构。  
必须分成四层：

1. 原始数据层
2. 抽取/规范化层
3. 图与检索投影层
4. 人类展示层

要求：

- 一次采集，多次利用
- 所有投影都可重建
- provenance 必须可追溯到原始文件、时间、会话、job、commit
- 中间层对象模型不能绑定某个框架

### 2.2 ledger 驱动状态机，graph 只做推理与检索

`open / in_progress / mitigated / closed` 的 authoritative state 必须留在事务型 ledger 中。  
Graph 只负责：

- 解释问题家族
- 关联证据
- 连接修复与验证
- 提供检索与导航

不能让 graph 反客为主决定 issue 状态。

### 2.3 先定义评估问题，再上图

没有评估指标的图系统只会变成“看起来高级”的附加复杂度。  
首批评估问题建议：

- agent 找到“当前最新可用修复路径”的成功率是否提高
- agent 找到“某类问题的上下游与历史演进”的耗时是否下降
- 人是否更容易理解一个问题家族的根因与验证状态
- 误连边/幻觉边比例是否可接受

## 3. 原始数据层

第一阶段不做新功能，先做深度 data audit。  
建议纳入的源：

### 3.1 ChatgptREST 运行源

- `state/jobdb.sqlite3`
  - `jobs`
  - `job_events`
  - `client_issues`
  - `client_issue_events`
  - `incidents`
- `artifacts/jobs/<job_id>/`
  - `request.json`
  - `events.jsonl`
  - `result.json`
  - `answer.*`
  - `conversation.json`
  - `run_meta.json`
- `artifacts/monitor/`
  - maint daemon
  - guardian
  - ui canary
  - verifier outputs

### 3.2 文档与演进源

- `docs/handoff_chatgptrest_history.md`
- `docs/issues_registry.yaml`
- `docs/dev_log/*.md`
- `docs/reviews/*.md`

### 3.3 代码与修复源

- `git log`
- `git show <commit>`
- GitNexus
  - symbol
  - process
  - impact
  - changed scope

### 3.4 跨仓库候选源

后续再扩展，不在第一阶段强绑定：

- Codex 历史会话导出
- planning
- research
- maint
- Obsidian vault

## 4. Canonical Schema（中间层对象）

这层是关键。  
建议先定义以下对象，不绑定具体图框架：

### 4.1 核心对象

- `Document`
  - 任意原文档、导出、Markdown、报告、spec、history entry
- `Episode`
  - 一段连续交互/执行过程，例如一次会话、一条 follow-up 链、一轮修复流程
- `Event`
  - 原始时序信号，例如 `conversation_url_conflict`、`WaitNoThreadUrlTimeout`
- `Atom`
  - 被抽象后的稳定结论、经验条目、修复知识
- `Entity`
  - provider、client、symbol、service、topic、project、host 等实体
- `Relation`
  - 实体/对象间的结构边
- `Evidence`
  - 可以追溯的原始证据片段
- `Topic`
  - 问题家族或主题域
- `Task`
  - 修复、验证、迁移、复盘等工作项
- `Version`
  - 文档版本、修复前后状态、代码版本

### 4.2 issue 域扩展对象

对 ChatgptREST 问题治理，建议保留显式对象：

- `Issue`
  - ledger authoritative record
- `Incident`
  - 运行态聚合对象
- `Verification`
  - 单元测试、回归、live、client acceptance 的验证记录
- `UsageEvidence`
  - 客户端真实成功使用记录

说明：

- 不建议一开始把 `Issue / Verification / UsageEvidence` 强塞进 `Atom`
- 这些对象对状态机和自动关闭有独立语义，值得单独存在

## 5. Provenance Contract

每条结论必须能回到：

- 原始文件路径
- 行号或片段
- job_id / issue_id / incident_id
- timestamp
- source system
- commit sha（如适用）
- extractor version

建议每个 `Evidence` 至少包含：

- `source_type`
  - `job_event` / `artifact` / `issue_event` / `doc` / `git` / `gitnexus`
- `source_ref`
  - 例如 `jobs/<job_id>/events.jsonl`
- `source_locator`
  - 行号、json path、symbol uid、commit range
- `captured_at`
- `content_hash`
- `excerpt`

要求：

- 图层中任何边都必须能追溯到 evidence
- 任何自动关闭动作都必须有 verification / usage evidence

## 6. 生命周期状态机

issue 状态继续保留：

- `open`
- `in_progress`
- `mitigated`
- `closed`

新的统一口径：

### 6.1 `mitigated`

满足以下条件即可：

- 已有 live 验证证据
- 证据与具体 issue 绑定
- 当前 live 路径没有再次触发该问题家族的已知 signal

等价于：

**live verified => mitigated**

### 6.2 `closed`

满足以下条件才关闭：

- 该 issue 已是 `mitigated`
- mitigated 之后，至少有 `3` 次符合条件的真实客户端成功使用
- 这 3 次属于该 issue family 的影响面
- 期间没有 recurrence

等价于：

**mitigated + 3 次 qualifying client success + no recurrence => closed**

### 6.3 `reopen`

任何时候，只要同 family 或同 fingerprint 再次复发：

- `mitigated -> open`
- `closed -> open`

## 7. 什么叫 qualifying client success

不能简单把任意 `completed` job 当成“可关闭证据”。  
建议定义：

- 来源必须是客户端真实使用
  - 不是 maint_daemon
  - 不是 guardian
  - 不是 repair/autofix
- 请求必须落在该问题影响面
  - same provider
  - same kind
  - same route family
- 必须 `completed`
- 且没有命中该问题家族的 signal

举例：

`gemini_followup_thread_handoff_family` 的 success evidence 应要求：

- `kind=gemini_web.ask`
- 属于 follow-up chain
- 已拿到稳定 thread / conversation 绑定
- 最终 completed
- 无：
  - `conversation_url_conflict`
  - `WaitNoThreadUrlTimeout`
  - 同家族 plan-stub / preamble 误判事件

## 8. 问题家族（Issue Family）

单条 symptom 不足以驱动可靠关闭。  
必须建立 family 层，把同一根因家族的多个 signal 聚合起来。

示例：

- `gemini_followup_thread_handoff_family`
  - `conversation_url_conflict`
  - `WaitNoThreadUrlTimeout`
  - same-conversation follow-up broken
  - plan-stub / preamble 误进入 completed

建议每个 issue 至少新增：

- `family_id`
- `family_version`
- `affected_provider`
- `affected_kind`

这样自动关闭就不是“某个单独错误 3 次没复发”，而是“整个问题家族在真实使用中已穿透验证”。

## 9. 图与检索投影层

### 9.1 先做 hybrid retrieval，不先 graph-first

对 ChatgptREST 来说，第一阶段更适合：

- FTS / hybrid retrieval 做主干
- property graph 做增强层

不建议第一阶段直接变成 heavy GraphRAG。

### 9.2 图层的定位

图层主要回答这些问题：

- 这个问题历史上出现过几次
- 它影响了哪些 provider / client / symbol / 文件
- 它由哪个 commit 修了
- 哪些 live 验证证明它已 mitigated
- 哪些客户端成功使用使它可关闭
- 这个问题和哪些问题属于同一家族

### 9.3 与 GitNexus 的关系

GitNexus 保持为代码图专长：

- symbol
- process
- impact
- changed scope

问题知识系统增加 ops/data 图：

- issue
- incident
- verification
- usage evidence
- doc
- commit
- client
- provider

通过 `File / Symbol / Commit / Job / Provider / Client` 做连接。

## 10. 展示层

建议至少导出两个首批视图：

### 10.1 Open Issue List

不要手写，改为自动生成：

- 机器版：
  - `artifacts/monitor/open_issue_list/latest.json`
- 人类版：
  - `docs/open_issue_list.md`

内容建议：

- issue_id
- family_id
- severity
- status
- current symptom
- latest evidence
- latest verification
- close progress
- next action

### 10.2 History Evolution Log

继续保留：

- `docs/handoff_chatgptrest_history.md`

但来源改成：

- 结构化 issue / verification / commit / doc refs 自动生成草稿
- 人工补根因总结和经验提炼

这能避免历史文档逐步漂移成纯手工回忆。

## 11. 建议的首批落地顺序

### 阶段 A：Data Audit

交付物：

- source inventory
- canonical schema 草案
- provenance contract
- evaluation questions

在这一阶段：

- 不做 graph-first 实现
- 不选定某个图库为真相源

并行 graph 审计会话已经给出一批高价值先验，可直接纳入本阶段基线：

- Codex 历史会话不是散乱日志，而是可重建会话链
  - 两套 HOME 下合计 3600+ 个 jsonl 会话
  - 可抽出：
    - `session_meta`
    - `turn`
    - `function_call`
    - `reasoning`
    - `ghost_snapshot`
    - `cwd`
  - 这意味着后续可以做“会话演进图”和经验写回，但不建议把它作为第一枪
- planning 比 maint 更适合做第一试点
  - 已确认存在现成中间层：
    - `_kb/index/manifest.json`
    - `index.sqlite`
    - `extracted/`
  - 结论：应优先复用 planning 的现有中间层，而不是为图检索另起一套抽取系统
- research 的最佳主源不是长报告，而是结构化材料
  - `claims/`
  - `inputs_index`
  - `EVIDENCE_MAP`
  - `CHANGELOG`
  - 这更适合构建“主题-断言-证据-缺口”图，而不是先从长篇报告抽边

### 阶段 B：Issue Domain Pilot

把 ChatgptREST 问题治理域作为一个中等复杂度试点，做：

- lifecycle 规则
- mitigation / close evidence model
- open issue list exporter
- history evolution draft generator

原因：

- 比 planning 噪音低
- 比 Codex 历史会话更结构化
- 能快速验证 provenance、family、verification、usage evidence 是否设计正确

### 阶段 C：planning / research pilot

在 schema 稳定后再做：

- planning 的版本演进图
- research 的主题图 / 缺口图

根据并行 graph 审计结果，推荐的整体试点顺序为：

1. planning：
   - `/vol1/1000/projects/planning/机器人代工业务规划/104关节模组代工_过程记录`
2. research：
   - `/vol1/1000/projects/research/archives/projects/2026-01-21_sc58_additive_3dp_humanoid/packages/2026-01-31_pro_report_regen_input_v1`
3. Codex 历史会话：
   - 先按单个 `cwd` 聚类抽样

这里的分工建议是：

- planning：验证版本、入口、产物、主题分叉、最新状态
- research：验证 claim / evidence / gap 图
- Codex 历史会话：验证 Episode / Turn / Tool / Reasoning 抽取质量
- ChatgptREST issue domain：验证 lifecycle / verification / usage evidence / close rule

换句话说，ChatgptREST 问题域不是“全局第一个 pilot”，但它是**统一 schema 下最适合尽快产品化落地的治理域**。

## 12. 技术路线建议

当前建议：

- 主路线：Hybrid retrieval
- 图路线：Property graph
- 抽取/实验层：可用 LlamaIndex PropertyGraphIndex 做 PoC
- GraphRAG heavy / global summarization：第二阶段再考虑
- Obsidian：做人类界面层，不做后端真相源

这与并行 graph 会话的技术结论一致：

- 不做“图替代检索”
- 做“统一中间层对象模型 + Hybrid RAG 主干 + Property Graph 增强 + Obsidian 人类界面层”
- 长期图后端优先考虑 Neo4j
- LlamaIndex PropertyGraphIndex 更适合 PoC / 抽取编排
- Microsoft GraphRAG 暂不作为第一阶段主系统

对 ChatgptREST 问题域，不建议：

- 一开始就 GraphRAG-first
- 把 ledger 状态机和图推理混在一起
- 把 close 规则写死在文档而不落到结构化对象上

## 13. 路径建议

建议未来固定这些路径：

- authoritative ledger：
  - `state/jobdb.sqlite3`
- open issue 导出：
  - `artifacts/monitor/open_issue_list/latest.json`
  - `docs/open_issue_list.md`
- 历史演进：
  - `docs/handoff_chatgptrest_history.md`
- known issue registry：
  - `docs/issues_registry.yaml`
- graph / retrieval snapshot：
  - `artifacts/knowledge/issue_graph/`
- 设计与评审文档：
  - `docs/reviews/`
- 实施过程记录：
  - `docs/dev_log/`

## 14. 下一步

不建议直接开始构图。  
下一轮应按以下顺序推进：

1. 做 source inventory
2. 写 canonical schema v0
3. 定义 issue family / verification / usage evidence 字段
4. 再做 `open issue list` 与 `history evolution` 两个 projection
5. 之后再决定 graph pilot

---

这份文档的定位是：  
**作为后续 data audit、schema 设计、issue knowledge pilot、graph pilot 的统一基线。**
