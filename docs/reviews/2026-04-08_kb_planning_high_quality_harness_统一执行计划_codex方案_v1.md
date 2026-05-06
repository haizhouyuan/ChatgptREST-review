# KB + Planning High-Quality Harness 统一执行计划 Codex方案 V1

Date: 2026-04-08

## 1. 目标

本计划把两条原本容易分散推进的主线收成一条统一执行线：

1. `KB / EvoMap / vector / promotion` 的知识治理
2. `planning / OpenClaw / advisor / coding-agent` 的高质量 harness

最终目标不是“再加一堆机制”，而是让系统在这两个层面同时达到可验证的生产级可用：

- 知识底座不再是“存而不用”
- planning 与 OpenClaw 高质量入口不再只是单个 vertical slice，而是可稳定回归、可持续扩展、可解释失败

## 2. 对 `claudeminmax` 的独立判断

### 2.1 适合让 `claudeminmax` 做的事

`claudeminmax` 适合做 **边界清晰、可并行、输出可核验** 的 sidecar 任务：

1. dataset 扩充
2. negative / boundary case 设计
3. 离线评测与报告汇总
4. 数据审计与 SQL 只读分析
5. prompt/closure 质量红队
6. harness case 生成与 markdown 证据整理

### 2.2 不适合让 `claudeminmax` 主导的事

以下工作必须由我自己主导，因为它们高度耦合主链、影响运行合同或需要统一架构判断：

1. retrieval surface 语义变更
2. promotion / groundedness / chain / metadata contract 变更
3. advisor / routes / scenario pack / task_intake 主链改动
4. 跨系统集成与最终 merge
5. 最终验收与 closeout

### 2.3 最终分工原则

一句话：

> `claudeminmax` 负责 sidecar research / eval / case generation / review；Codex 负责主链设计、主链代码、集成、验收与最终判断。

## 3. 总体执行结构

本轮统一计划拆成 4 个工作流，但只维护 **一个主计划**：

### Workstream A：KB / EvoMap 治理底座

目标：

- 阻止垃圾继续入库
- 疏通 planning 知识的 candidate / active 提升
- 修复 metadata 与 promotion 基础健康度

### Workstream B：planning 高质量 harness

目标：

- 把目前仅覆盖 `visit_cooperation_prep` 的高质量 vertical 加固成真正的质量门禁
- 扩展 raw ingress / closure / learning 的测试厚度

### Workstream C：OpenClaw / planning / KB 联动

目标：

- 让高质量 harness 真正吃到治理后的知识底座
- 避免“入口变聪明了，但 context 还是脏/薄/错”

### Workstream D：统一验收与运行可观测性

目标：

- 让每个子系统的成功标准不是“改完了”，而是“可持续观测、可重复验证、可故障定位”

## 4. 详细执行计划

## Phase 0：冻结边界与基线

### P0.1 冻结当前事实基线

Owner:

- Codex

动作：

1. 冻结当前 live 数字：
   - atoms/status/promotion_status 分布
   - groundedness / chain_id / canonical_question / valid_from 覆盖
   - KB FTS/vector/registry 覆盖
   - query/retrieval/feedback 覆盖
2. 冻结当前 planning harness 基线：
   - phase10 现有 2 case
   - readiness pack 现状
   - live route / clarify / closure 行为

产出：

- 基线报告
- 对比用 acceptance ledger

验收：

- 后续任何优化都有 before/after 对比，不再凭印象判断

### P0.2 冻结 plane 合同

Owner:

- Codex

动作：

把知识系统显式冻结为三条 plane：

1. `Curated plane`
   - reviewed runtime pack
2. `Promoted plane`
   - EvoMap active / candidate
3. `Evidence plane`
   - KB hybrid

每条 plane 明确：

- source family allowlist
- retrieval surface
- prompt 注入上限
- freshness / quality 指标

验收：

- 文档与代码注释对齐
- 后续实现不再混淆 runtime pack、promotion plane、KB evidence plane

## Phase 1：止血与 metadata 健康修复

### P1.1 垃圾 atom 家族治理

Owner:

- Codex：策略与实现
- `claudeminmax`：家族识别样本、归档候选报告

动作：

1. 识别垃圾家族：
   - `tool.completed` event atoms
   - 通用标题类：`结论`、`Test Results`、`Files`
   - `.venv` / 纯命令 / 低信息路径片段
2. 先做 dry-run family report
3. 再做可逆 `archive`，不做物理删除
4. 给 `activity_extractor` 与 `BaseExtractor` 增加门禁：
   - 最短长度
   - 标题特异性检查
   - 路径黑名单
   - family / content hash 去重

并行策略：

- `claudeminmax` 负责从现有 DB 抽样、给出垃圾族清单与误伤风险
- Codex 按清单落实现与 dry-run runner

测试：

- extractor unit tests
- archive dry-run snapshot tests
- negative tests：高价值短答案、命令型有价值文档不应误杀

验收：

- 新一轮 ingest 后垃圾族新增量接近 0
- 归档动作可解释、可回滚

### P1.2 metadata 回填

Owner:

- Codex
- `claudeminmax`：只读分析与 mismatch 审核

动作：

1. 回填 `valid_from`
2. 回填 / 生成缺失的 `canonical_question`
3. 保留 `scope_project` 风险边界，不做 broad blind write

测试：

- migration dry-run
- spot checks on planning families
- regression：retrieval time decay 不应恶化

验收：

- `valid_from` 缺失率显著下降
- `canonical_question` 缺失率显著下降

## Phase 2：promotion / groundedness / chain 疏通

### P2.1 family-aware groundedness

Owner:

- Codex

动作：

1. 把 groundedness 从单一统一权重改为 family-aware：
   - planning：降低或跳过 `code_symbol`
   - code/procedure：保留 code symbol 校验
2. 对 planning reviewed families 先 sample scoring
3. 用结果校准阈值，但不走 `quality_auto = groundedness` shortcut

测试：

- groundedness checker unit tests
- planning vs code atom score expectation tests
- sampled audit diff

验收：

- `groundedness_audit` 覆盖显著增长
- planning 高质量 atom 不再因 code-symbol 误伤大量挂掉

### P2.2 bulk refine + candidate/active movement

Owner:

- Codex：runner / scheduler / gate
- `claudeminmax`：throughput audit / failure distribution review

动作：

1. 把 planning bulk scoring / promotion runner 做成稳定运行面
2. 记录 bucket 级吞吐：
   - scanned
   - scored
   - candidate promotions
   - active promotions
   - failures
3. 明确 reviewed maintenance 与 bulk promotion 的区别

测试：

- runner smoke
- timer execution evidence
- inventory before/after

验收：

- `candidate + active` 有持续移动
- audit 不再停滞
- timer 运行与实际 inventory movement 一致

### P2.3 chain_builder 启用

Owner:

- Codex

动作：

1. 在 metadata 回填后运行 chain backfill
2. 建立 supersession / chain 语义
3. 让旧版本可降级、可解释

测试：

- chain builder unit tests
- duplicate family chain formation tests

验收：

- `chain_id_nonempty` 不再为 0
- 可观察到 version family / superseded 关系

## Phase 3：planning 高质量 harness 加固

### P3.1 扩充 phase10 质量数据集

Owner:

- `claudeminmax`：主责 case 设计
- Codex：最终筛选、接入 harness

动作：

把当前 2 个样本扩到 10-15 个 case，至少包含：

1. 正例
   - 来访准备
   - 合作洽谈
   - 供应商交流
   - 资本牵线会前准备
2. 负例
   - 内部周会准备
   - 纯项目诊断
   - 普通研究请求
3. 边界例
   - 投诉处理 vs visit prep
   - 质量问题来访 vs project diagnosis

测试：

- dataset snapshot tests
- multi-ingress validation

验收：

- phase10 不再只有 2 个样本
- 能稳定区分正例/负例/边界例

### P3.2 interaction learning 加固

Owner:

- Codex：主实现
- `claudeminmax`：marker / signal coverage review

动作：

1. 扩充 correction markers：
   - 太长了
   - 太短了
   - 重点不对
   - 先告诉我怎么回对方
   - 我要的不是这个
   - 质量不够高
2. 扩 signal 维度：
   - brevity preference
   - reply-first preference
   - focus correction
3. 加 negative tests
4. 设计衰减 / 冲突解决，而不是简单 last-write-wins
5. 预留 user-scoped 演进点

测试：

- unit tests for positive triggers
- negative tests for false positives
- merge/decay conflict tests

验收：

- 真实高频纠正不再大量漏掉
- 普通对话不会误触发 correction 学习

### P3.3 live end-to-end harness

Owner:

- Codex
- `claudeminmax`：red-team prompts 与结果复核

动作：

1. 新增 visit/cooperation prep 的 live E2E gate
2. 真正走：
   - ingress
   - normalization
   - route
   - execution lane
   - closure
3. 记录：
   - profile
   - clarify behavior
   - chosen executor family
   - closure sections

验收：

- 至少 1 条 live visit/cooperation prep 主链稳定通过
- 结果不是只验证 contract，而是验证完整闭环输出

## Phase 4：框架泛化

### P4.1 可插拔 ingress detector framework

Owner:

- Codex

动作：

把 `_derive_ingress_normalization()` 从特例检测升级成 detector registry：

1. detector 接口
2. detector 优先级
3. detector 冲突解决
4. detector explainability

第一批 detectors：

- `visit_cooperation_prep`
- `internal_meeting_prep`
- `competitor_scan`
- `customer_issue_response`

测试：

- detector unit tests
- mixed-signal conflict tests

验收：

- 新任务族不再必须直接改 task_intake 核心 if-else

### P4.2 新任务族 profile 扩展

Owner:

- Codex：主实现
- `claudeminmax`：样本与 closure review

动作：

新增 2-3 个高频 profile：

1. 竞品分析
2. 客户投诉/问题处理
3. 内部周会准备

每个 profile 都要有：

- normalization 信号
- clarify 策略
- route / execution preference
- closure sections
- acceptance cases

验收：

- 不再只有 `visit_cooperation_prep` 一个高质量 vertical

## Phase 5：KB / planning / OpenClaw 联动

### P5.1 retrieval surface 与 harness 对齐

Owner:

- Codex

动作：

1. planning high-quality harness 必须吃到治理后的知识 plane
2. 新增 diagnostics：
   - 来源是 curated / promoted / evidence 哪一条 plane
   - 是 active / candidate / staged_fallback 哪一层
3. 对 planning 显式任务开放受控 candidate/staged fallback，而不是直接改 USER_HOT_PATH

测试：

- retrieval explainability tests
- planning explicit query tests
- gold benchmark with real asks

验收：

- 高质量 harness 的成功，不再只是入口策略成功，而是真正带上了更好的知识上下文

### P5.2 KB hybrid 稳定化

Owner:

- Codex：运行时统一、检索合同
- `claudeminmax`：probe case 与质量 review

动作：

1. 统一 `.venv` 与普通脚本运行时的 embedding 行为
2. 扩充高价值 vectors：
   - active + candidate
   - reviewed planning docs
3. 提高 provenance 完整率

测试：

- kb probe
- vec-only / hybrid hit review
- source_path/project completeness checks

验收：

- 向量不再只是偶尔可用
- 命中不再主要是泛 research 噪音

## Phase 6：统一验收

### 6.1 测试矩阵

必须同时跑：

1. unit
   - extractor / groundedness / interaction learning / detector / scenario pack
2. contract
   - task intake / route / readiness / multi-ingress validation
3. integration
   - promotion runner / runtime pack refresh / kb probe
4. live
   - 至少 1 条 visit prep E2E
   - 至少 1 条 planning explicit knowledge E2E

### 6.2 验收标准

#### A. 知识治理

1. 垃圾家族新增量明显下降
2. `valid_from` / `canonical_question` 缺失率下降
3. `groundedness_audit` 覆盖增长
4. `candidate + active` 有持续移动
5. `chain_id` 不再为 0

#### B. planning harness

1. phase10 扩展数据集通过
2. negative / boundary cases 不误判
3. interaction learning 触发覆盖明显提升
4. live E2E 稳定通过

#### C. 联动效果

1. planning query 的 context 质量提升可被解释
2. OpenClaw 输入到 closure 的完整链路稳定
3. 错误时能解释失败在 ingress、route、executor 还是 knowledge plane

## 5. 并行执行建议

### 批次 1：可立即并行

- Codex：
  - P1.1 垃圾入库门禁
  - P1.2 metadata 回填设计
  - P3.2 interaction learning 加固设计
- `claudeminmax`：
  - phase10 dataset 扩展草案
  - negative / boundary case 设计
  - 垃圾 atom 家族抽样报告

### 批次 2：需要 Codex 主链落地后并行

- Codex：
  - P2.1 family-aware groundedness
  - P4.1 detector framework
- `claudeminmax`：
  - groundedness score review
  - harness red-team review
  - closure quality rubric review

### 批次 3：集成与 live 前

- Codex：
  - P5 联动与 live gate
- `claudeminmax`：
  - live prompt pack
  - post-run critique

## 6. 我自己的执行边界

我自己负责：

1. 主链代码改动
2. 知识合同与 retrieval 语义
3. promotion / groundedness / chain 关键变更
4. OpenClaw / planning lane 路由与 closure 主链
5. 最终测试、最终 merge、最终验收

我不会把以下内容外包给 `claudeminmax`：

1. routes/task_intake/scenario_packs 主链 merge 决策
2. promotion gate 语义决策
3. retrieval surface 默认行为改动
4. 最终 closeout

## 7. 最终建议

如果要启动这轮执行，我建议：

1. 以这份统一计划作为唯一主计划
2. 允许 `claudeminmax` 做 sidecar，并且只做边界清晰的任务
3. 不再新增抽象层命名，不再产出 superseding strategy docs
4. 先做 vertical 加固，再做框架泛化，再做知识联动扩展

一句话冻结：

> 这轮最正确的路径不是“再设计一个 Task OS”，而是把已有执行基础设施上的策略层、质量门禁和知识底座一起做实，并且用 Codex 主导主链、`claudeminmax` 并行补 sidecar。 
