# KB + Planning High-Quality Harness 统一执行计划 Codex方案 V5

## 1. 修订背景

`v4` 之后又做了一轮独立核验。结论是：

1. `metadata / harness / live ingress gate` 已经真实完成。
2. `promotion / groundedness / chain` 的代码与 smoke 已有，但此前没有把 live 数据面真正跑实。
3. 本版 `v5` 的唯一目标，是把 `Phase 2` 从“代码存在”推进到“生产 DB 聚合数字真实变化”。

本版不再扩任务族，不再发明新子系统，也不把向量库扩容和 query semantic bridging 混进同一轮收口。

## 2. 冻结后的执行范围

### 2.1 本轮必须完成

1. `planning bulk groundedness scoring` 在 live DB 上真实写入。
2. `candidate -> active` promotion 在 live DB 上真实发生。
3. `chain_id / chain_rank / is_chain_head / superseded_by` 在 live DB 上真实回填。
4. 验收必须包含 before/after DB 聚合数字。

### 2.2 本轮明确不混入

1. 全量 EvoMap 向量重建。
2. 新任务族横向扩展。
3. 业务 query semantic bridging 的新框架。

## 3. 系统边界冻结

### 3.1 EvoMap

- DB: [data/evomap_knowledge.db](/vol1/1000/projects/ChatgptREST/data/evomap_knowledge.db)
- 默认 retrieval surface: [retrieval.py](/vol1/1000/projects/ChatgptREST/chatgptrest/evomap/knowledge/retrieval.py)
- prompt 注入入口: [context_assembler.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/context_assembler.py)

### 3.2 Planning reviewed runtime pack

- curated overlay，不等于 EvoMap 默认热路径
- planning 显式任务可用，但不是默认 user hot path 的替代物

### 3.3 KB Hub

- DB: [~/.openmind/kb_search.db](/home/yuanhaizhou/.openmind/kb_search.db), [~/.openmind/kb_vectors.db](/home/yuanhaizhou/.openmind/kb_vectors.db), [~/.openmind/kb_registry.db](/home/yuanhaizhou/.openmind/kb_registry.db)
- 文档级检索与 evidence plane
- 本轮不做 KB Hub / EvoMap 合并

## 4. 执行内容

### 4.1 Groundedness / promotion live apply

使用：
- [run_planning_bulk_groundedness_promotion.py](/vol1/1000/projects/ChatgptREST/ops/run_planning_bulk_groundedness_promotion.py)

实际 live apply：
- `20260408T135900Z`
- `20260408T140337Z`
- `20260408T140754Z`

family-aware 权重冻结：
- planning: `path 0.40 + staleness 0.30 + service 0.15 + code_symbol 0.15`
- code/procedure: `path 0.40 + service 0.20 + staleness 0.15 + code_symbol 0.25`

### 4.2 Chain live apply

直接用旧版 `build_chains()` live apply 有风险：
- 会回写 `promotion_status`
- 会把已存在的 `active/candidate` 语义覆盖成 `candidate/superseded`

因此本轮新增安全模式：
- [chain_builder.py](/vol1/1000/projects/ChatgptREST/chatgptrest/evomap/knowledge/chain_builder.py)
- [run_evomap_chain_backfill.py](/vol1/1000/projects/ChatgptREST/ops/run_evomap_chain_backfill.py)

live 模式默认：
- `apply_promotion_semantics = false`
- 只回填 `chain_id / chain_rank / is_chain_head / superseded_by`
- 不重写 `promotion_status / promotion_reason`

实际 live apply：
- [20260408T140142Z](/vol1/1000/projects/ChatgptREST/artifacts/monitor/evomap_chain_backfill/20260408T140142Z/summary.json)

## 5. 验收标准

### 5.1 DB 聚合必须变化

至少满足：

1. `groundedness_audit` 明显增长
2. `active` 明显增长
3. `candidate` 明显增长
4. `chain_nonempty > 0`

### 5.2 保护性约束

1. live chain apply 不得覆盖既有 `active/candidate/archived`
2. `answer_feedback` 通路不能回退
3. `visit_cooperation_prep` live gate 不得回归

## 6. 实际结果

### 6.1 全库 before / after

- `active`: `243 -> 816`
- `candidate`: `538 -> 4312`
- `groundedness_audit`: `335 -> 3445`
- `chain_nonempty`: `0 -> 103259`

### 6.2 planning before / after

- `planning_active`: `242 -> 815`
- `planning_candidate`: `538 -> 4312`
- `planning_staged`: `35129 -> 30782`
- `planning_groundedness_nonzero`: `375 -> 2308`

## 7. 新增证据包

- [planning bulk live 1](/vol1/1000/projects/ChatgptREST/artifacts/monitor/planning_bulk_groundedness_promotion/20260408T135900Z/summary.json)
- [planning bulk live 2](/vol1/1000/projects/ChatgptREST/artifacts/monitor/planning_bulk_groundedness_promotion/20260408T140337Z/summary.json)
- [planning bulk live 3](/vol1/1000/projects/ChatgptREST/artifacts/monitor/planning_bulk_groundedness_promotion/20260408T140754Z/summary.json)
- [chain live apply](/vol1/1000/projects/ChatgptREST/artifacts/monitor/evomap_chain_backfill/20260408T140142Z/summary.json)

## 8. 本轮之后的真实边界

本轮已经把 `promotion / chain` 的 live 数据面跑实。

但下面两件事仍然不应被夸大成“已完成”：

1. 扩容后的 EvoMap 向量重建
2. 对“绿源 / 钛虎 / 来访准备”这类业务 query 的 semantic bridging

当前已确认的原料稀疏事实：
- `绿源` 命中仅 `4`
- `钛虎` 命中 `0`
- `来访` 命中 `6`

所以本轮正确口径是：

**底层 promotion pipeline 已从假通变成真通；但业务 query 召回质量还没有达到终局。**
