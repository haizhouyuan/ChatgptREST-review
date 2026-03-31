---
title: Planning Lineage and EvoMap Import Strategy
version: v1
updated: 2026-03-11
status: completed
artifact_workspace: /vol1/1000/projects/ChatgptREST/artifacts/monitor/planning_history_agent_teams/20260311T080541
planning_repo: /vol1/1000/projects/planning
---

# 结论先行

对 `planning` 仓库，最该先做的不是再建一套向量库，而是先把 **lineage graph** 做出来，再把高价值结果分层投影进 EvoMap。

原因很明确：

1. `planning` 仓库已经有本地全文索引 `_kb/index/index.sqlite`，能回答“在哪里提过”。
2. 当前真正困难的问题不是关键词定位，而是：
   - 哪个文档家族从哪个输入演进而来；
   - 哪个 review pack 对应哪轮模型运行；
   - 哪个 `99_最新产物` 才是当前生效版；
   - 哪些差异是可复用经验，哪些只是历史留痕。
3. 这类问题本质上是 **谱系关系问题**，不是纯相似度召回问题。

本次梳理后，建议把 `planning` 接入 EvoMap 的方式收敛为：

- `archive_only`: 原始 review pack、中间版本、对话与日志、受控资料
- `review_plane`: version family、review loop、model run、latest output、差异判定
- `service_candidate`: 当前稳定模板、冻结口径、经过 review 的总结稿
- `lesson / procedure / correction`: 从版本差异与 review 链中蒸馏，不直接从原文整段切入

# 研究范围与方法

## 仓库体量

- `all_files = 28086`
- `text_like_files = 22289`
- 重点顶层目录：
  - `减速器开发`
  - `机器人代工业务规划`
  - `docs`
  - `aios`
  - `十五五规划`
  - `预算`

## 采用的方法

不是“平均通读 2.2 万文本文件”，而是两层并行：

1. **domain slices** 识别高价值文件族和历史演进
2. **relation extractor** 横向抽 `VersionFamily / ReviewPack / ModelRun / LatestOutput` 关系

同时用 deterministic bootstrap 抽取：

- `bootstrap_version_edges.tsv`: `1025` 条
- `bootstrap_latest_output_edges.tsv`: `351` 条
- `bootstrap_model_run_edges.tsv`: `321` 条

再用 Claude Code teams 跑窄切片，结合人工/本地复核做 synthesis。

# planning 历史主脉络

## Era 0: 规划启动与原始愿景期（2025-10）

主线特征：

- 出现最早的事业部规划、愿景定位、人力与招聘规划
- 这批文档不是高度结构化流程产物，而是后续所有规划线的“源头语义”

高价值家族：

- `愿景与定位`
- `业务规划`
- `具身智能事业部研发人力资源规划与招聘计划`

EvoMap 判断：

- 原文多进 `archive_only` / `review_plane`
- 抽出来的“事业部定位原则”“能力边界口径”适合做 `lesson` / `procedure`

## Era 1: 模板与治理底座成形（2025-12）

主线特征：

- 预算模板体系开始形成
- 十五五规划开始引入打包与归档
- 管理制度、专项小组规则、review pack 形式开始稳定

高价值家族：

- `预算模板`
- `15th-plan-pack`
- `专项小组工作管理办法`
- `十五五规划小组管理办法`

EvoMap 判断：

- 模板本体适合 `service_candidate`
- 打包归档与中间 review material 适合 `archive_only`
- “先模板、再摘要、再评审、再出稿”的流程可提炼为 `procedure`

## Era 2: 业务规划爆发期（2026-01）

这是 `planning` 最核心的产能爆发阶段，形成了三条关键业务线：

1. `104关节模组代工`
2. `60系列PEEK模组代工`
3. `十五五规划 / 预算 / 对内对外稿`

共同特征：

- 输入材料被整理成最小材料包
- 经 ChatGPT Pro / Gemini 等模型多轮评审
- 拆成模块化输出
- 汇总成领导稿 / 客户稿 / 当前最新产物

### 104 业务线

主链：

`本地材料消化 -> 会话摘要 -> 104模组代工规划 -> 场地设备人员规划 -> 可行性研究 -> 领导执行版 -> 客户沟通稿 -> 99_最新产物`

关键结论：

- 这条线已经具备较完整的“输入-评审-输出-交付”链
- `07_领导规划报告/outputs/*_可执行版_*.md`
- `06_可行性研究报告/outputs/投决工作流工具包_v0.2.md`
- `99_最新产物/07_客户沟通材料_LM/客户沟通稿_*.md`
  这些都可以作为 `service_candidate`

### 60 业务线

主链：

`01_消化本地文件 -> 02_需求澄清与模块拆解 -> 03_分模块产出(M1-M8) -> 04_汇总报告`

关键结论：

- 这条线体量不大，但流程极规整
- `00_meta`、`Review Pack`、`M1-M8` 模块化产出、领导版汇总报告很适合作为流程模板
- 中间态 `conversation/events/debug` 明显不该进 service plane

### 十五五规划 / 预算 / 组织线

主链：

`市场调研 / 历史业务数据 / 人力与制度输入 -> 初稿v0.1 -> v0.2 -> v0.3 -> v0.4 -> 领导审阅稿 / 模块负责人执行稿 / 对外沟通稿`

关键结论：

- 十五五规划是典型的 version family 丰富、latest output 明确、review pack 浓度高的文档线
- 预算模板与预算概览/明细构成另一条标准输入输出链
- 面试/受控资料线需要单独敏感性标注，默认不进 service plane

## Era 3: 治理与平台化期（2026-02）

主线特征：

- `skills-src`、`_kb`、`docs/记忆治理与跨库归档`、`aios/` 同时成熟
- `planning` 仓库开始不只是业务规划仓库，而是兼具治理与工具层的“规划系统仓库”

关键家族：

- `planning-pro-review-loop`
- `ppt-banana-review-loop`
- `_kb` 模板、packs、index
- `docs/reports/index_governance/cron/*`
- `aios/*`

EvoMap 判断：

- `_kb` 与 `aios` 的稳定规范适合进 `review_plane`
- 真正冻结后的方法论文档与模板可进 `service_candidate`
- 每日治理 cron、快照、git status 长文本只适合 `archive_only`

## Era 4: 减速器 / PEEK review loop 深水区（2026-02-16 至 2026-02-25）

这是最接近“研究-评审-仿真-双模复核-冻结”的技术性闭环。

分成两条线：

1. `60关节模组研发主线`
   - `材料整理 -> Pro评审R0 -> M0-M7模块产出 -> 总报告v0.1/v0.2/v0.3`
2. `PEEK摆线齿轮 review pack 主线`
   - `H1假设与STEP抽取 -> 拟合仿真代码 -> 真齿廓提取 -> 无人值守闭环 -> 双模确认R1 -> 双模追问R2 -> 双模复核R3-R8 -> 冻结R8与R9触发条件`

其中第 2 条最值得进 EvoMap，但不是把全部 `_review_pack` 塞进去，而是要抽成：

- `correction`: 装配假设/模型边界/参数冻结的纠错链
- `procedure`: STEP 提取、仿真、双模复核、冻结口径流程
- `lesson`: “趋势筛选 vs 高保真验证”“默认不进下一轮，触发才升级”等经验

# 高价值文件族与关系模型

## 建议的节点类型

- `Document`
- `VersionFamily`
- `ReviewPack`
- `ModelRun`
- `LatestOutput`
- `ProcessFamily`

## 建议的边类型

- `SUPERCEDES`
- `SUPPLEMENTS`
- `PARALLELS`
- `DERIVED_FROM`
- `REVIEWED_IN`
- `GENERATED_BY_MODEL_RUN`
- `IS_LATEST_OF`
- `GUIDES_REVISION_OF`
- `ARCHIVE_OF`
- `CORRECTS`

## 当前最值得保留的 28 个 curated families

已在 artifact 中输出到：

- `/vol1/1000/projects/ChatgptREST/artifacts/monitor/planning_history_agent_teams/20260311T080541/final_v1/planning_lineage_family_registry.tsv`

其中重点包括：

- 治理/系统：
  - `governance_entry_root`
  - `kb_index_system`
  - `memory_governance_docs`
  - `aios_platform_specs`
- 组织/预算：
  - `fifteen_plan_current_drafts`
  - `budget_templates`
  - `budget_outputs`
  - `interview_controlled_reports`
- 104：
  - `b104_local_digest_input`
  - `b104_site_plan`
  - `b104_feasibility`
  - `b104_exec_report`
  - `b104_customer_comm`
  - `b104_latest_outputs`
- 60：
  - `b60_digest_reviewpacks`
  - `b60_requirements_split`
  - `b60_module_outputs`
  - `b60_summary_reports`
- 减速器：
  - `reducer_material_packs`
  - `reducer_pro_review_r0`
  - `reducer_module_outputs`
  - `reducer_summary_report`
- PEEK review loop：
  - `peek_reviewpack_autonomous_loop`
  - `peek_reviewpack_sim_code`
  - `peek_reviewpack_real_profile_consult`
  - `peek_reviewpack_dual_confirm`

# planning -> EvoMap 的分层入库策略

## 1. archive_only

默认只归档，不进在线服务面的内容：

- `_review_pack/*.zip`
- 中间版本文档
- `chatgptpro/answer_*.md`
- `conversation_*.json`
- `events_*.jsonl`
- `debug_*.html/png/txt`
- 原始图纸/STEP/PDF/XLSX/CSV 证据
- 面试简历、受控资料、脱敏映射执行细节
- 每日治理 cron 快照与全量 git status 文本

## 2. review_plane

应该先进 review plane 的内容：

- `VersionFamily`
- `LatestOutput`
- `ReviewPack`
- `ModelRun`
- `REQUEST / SUMMARY / RESULT / MANIFEST / CHANGELOG`
- 十五五规划版本族
- 104 / 60 / reducer 的主流程与 review loop 索引
- `_kb` 与 `aios` 的方法论/系统规范

## 3. service_candidate

可以优先尝试进入 service candidate 的内容：

- `104` 的执行版规划报告、客户沟通稿、投决工作流工具包
- `60` 的四阶段流程规范、领导版汇总报告、M1 停止线治理
- `reducer` 的 M0 裁决体系、Gate+RACI、外协量测规范、总报告稳定版
- `预算模板`
- `十五五规划` 的当前冻结稿与对内/对外成稿

## 4. lesson / procedure / correction

这三类不能靠 raw 文本直接切，必须从版本差异和 review 链抽。

### lesson 候选

- 模糊承诺必须绑定前提条件与证伪条件
- 低成本趋势筛选与高保真验证要分层
- Review Pack 应逐轮补充信息，而不是每轮重造上下文
- 默认不升级下一轮，只有触发条件满足才继续扩展搜索空间
- StopLine / Gate / 冻结口径必须前置写入输入包

### procedure 候选

- 四阶段规划流程：材料包 -> 需求澄清 -> 模块产出 -> 汇总报告
- Review Pack 构建 SOP：最小材料包、README、REQUEST、MODEL_SPEC、results
- 双模复核流程：确认 -> 追问 -> 复核 -> 结果与指导 -> 下一轮触发条件
- planning 仓库里 latest output 的归档与 release 标记流程

### correction 候选

- 评审轮次过多说明输入包不够收敛，不能只靠多轮问模型补
- 中间态 answer/debug 文件不应直接进入经验层
- 同一技术问题的最终价值不在原始 H1/H2 假设文本，而在“为什么冻结成当前主线”

# 当前系统状态判断

## planning 自身

- 已具备本地全文检索能力
- 尚未具备仓内可直接用的 lineage graph / 向量检索
- 最适合补的是谱系图，而不是盲目 embedding 全仓

## 对 EvoMap 的意义

当前最合理的接入方式不是“全量导 planning 原文”，而是：

1. 先把 `Document / VersionFamily / ReviewPack / ModelRun / LatestOutput` 建成 lineage graph
2. 再把高价值稳定内容投影到 EvoMap
3. 再把 version diff 与 review 决策蒸馏成 `lesson / procedure / correction`

# 后续执行建议

## P0

- 把 artifact 中的 `family_registry / edges / mapping_candidates` 固化成正式 import contract
- 给 `planning` 增加独立的 lineage extraction 脚本或 notebook，不直接往 service plane 写

## P1

- 对 `十五五规划 / 预算 / 104 / 60 / reducer / governance` 6 大主线做正式 family registry
- 把 `bootstrap_version_edges / bootstrap_latest_output_edges / bootstrap_model_run_edges` 升格为 review-plane candidate edges

## P2

- 为 `planning` 增加 `version_family` 与 `latest_output` 的显式映射表
- 加入 `sensitivity_level`，把面试/受控资料默认挡在 service plane 外

## P3

- 针对 `PEEK reviewpack` 单独做一个“review loop -> lesson/procedure/correction”抽取器
- 这条线的经验密度高，但原始文件太杂，不应直接入库

# 产物位置

- bootstrap summary:
  - `/vol1/1000/projects/ChatgptREST/artifacts/monitor/planning_history_agent_teams/20260311T080541/final_v1/planning_lineage_graph_bootstrap_v1.md`
- family registry:
  - `/vol1/1000/projects/ChatgptREST/artifacts/monitor/planning_history_agent_teams/20260311T080541/final_v1/planning_lineage_family_registry.tsv`
- curated edges:
  - `/vol1/1000/projects/ChatgptREST/artifacts/monitor/planning_history_agent_teams/20260311T080541/final_v1/planning_lineage_edges.tsv`
- EvoMap mapping candidates:
  - `/vol1/1000/projects/ChatgptREST/artifacts/monitor/planning_history_agent_teams/20260311T080541/final_v1/planning_evomap_mapping_candidates.tsv`

