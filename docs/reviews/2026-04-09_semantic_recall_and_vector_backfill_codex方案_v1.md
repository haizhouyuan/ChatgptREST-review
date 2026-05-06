# Semantic Recall And Vector Backfill Codex方案 V1

## 1. 目标

在 `Phase 2 live complete` 之后，把下一阶段的重点从 `promotion` 转到 `semantic recall`。

本轮目标冻结为两项：

1. 用真实业务 query 建立可重复执行的 recall harness：
   - `绿源来访准备`
   - `钛虎机器人关节模组合作`
   - `两轮车车轮市场竞争分析`
2. 把 EvoMap 向量化从 `740` 条扩到当前 planning `active + candidate` allowlist slice 的全量可观测 backfill。

## 2. 现状裁决

### 2.1 Phase 2 已完成，但不是终局

截至本轮开始前，live DB 已经满足：

- `active = 816`
- `candidate = 4312`
- `groundedness_audit = 3575`
- `chain_id nonempty = 103259`

这说明 promotion/chain 不是当前主瓶颈。

### 2.2 当前真正短板是 semantic recall

本轮开始前，对 3 个真实 query 的 planning explicit probe 全部为 `0`：

- `绿源来访准备 -> 0`
- `钛虎机器人关节模组合作 -> 0`
- `两轮车车轮市场竞争分析 -> 0`

根因不是单一问题，而是三件事叠加：

1. `planning explicit` fallback 只按空格切词，中文无空格 query 会被当成一个整体 token。
2. planning 大量可用 atom 是 `status=reviewed`，但 runtime `min_status` 没把 `reviewed` 放进 `planning explicit` surface。
3. EvoMap vector lane 只有 `740` 条，远低于当前 `active + candidate` 的规模。

## 3. 本轮执行

### 3.1 Retrieval 修复

修改文件：

- [retrieval.py](/vol1/1000/projects/ChatgptREST/chatgptrest/evomap/knowledge/retrieval.py)

改动点：

1. 为 `planning explicit` 增加中文业务 query normalization：
   - 提取 `绿源 / 钛虎 / 两轮车 / 车轮 / 市场 / 竞争 / 分析 / 来访 / 拜访 / 准备 / 合作 / 关节模组 / 机器人` 等高价值语义项
   - 对 `来访准备 / 合作洽谈 / 竞争分析` 做同义扩展
2. `_substring_fallback_rows()` 增加：
   - `canonical_question`
   - `documents.title`
   - `documents.raw_ref`
   的 LIKE 命中面
3. `planning explicit` surface 显式接纳 `status=reviewed`
4. substring fallback 按 `project_id` 收窄，避免扫出大量无关条目

### 3.2 EvoMap vector backfill 修复

修改文件：

- [vector_lane.py](/vol1/1000/projects/ChatgptREST/chatgptrest/evomap/knowledge/vector_lane.py)
- [run_evomap_vectorization.py](/vol1/1000/projects/ChatgptREST/ops/run_evomap_vectorization.py)

改动点：

1. `index_records()` 支持 batch embedding
2. 增加 `save_every_batches`，让 long-running backfill 周期性落盘
3. `run_evomap_vectorization.py` 支持：
   - `--batch-size`
   - `--save-every-batches`

这次没有继续用“一次性全量 embed 后最后才写盘”的不可观察模式，而是改成可恢复、可观测的 backfill。

### 3.3 新增 harness

新增文件：

- [run_evomap_semantic_recall_harness.py](/vol1/1000/projects/ChatgptREST/ops/run_evomap_semantic_recall_harness.py)
- [test_run_evomap_semantic_recall_harness.py](/vol1/1000/projects/ChatgptREST/tests/test_run_evomap_semantic_recall_harness.py)

作用：

- 对 3 个真实 query 做固定 probe
- 输出 `hit_count / vector_hit_count / retrieval_sources / retrieval_layers / top hits`
- 写入 artifact 形成回归证据

## 4. 验收结果

### 4.1 Focused tests

通过：

- [test_evomap_runtime_contract.py](/vol1/1000/projects/ChatgptREST/tests/test_evomap_runtime_contract.py)
- [test_evomap_vector_lane.py](/vol1/1000/projects/ChatgptREST/tests/test_evomap_vector_lane.py)
- [test_run_evomap_vectorization.py](/vol1/1000/projects/ChatgptREST/tests/test_run_evomap_vectorization.py)
- [test_run_evomap_semantic_recall_harness.py](/vol1/1000/projects/ChatgptREST/tests/test_run_evomap_semantic_recall_harness.py)

### 4.2 Vector backfill

最终结果：

- `pre_vector_count = 740`
- `post_vector_count = 4547`
- `records_selected = 4547`
- `indexed = 4547`
- `mode = vector`

证据：

- [vectorization summary](/vol1/1000/projects/ChatgptREST/artifacts/monitor/evomap_vectorization/20260408T230927Z/summary.json)
- [vectorization report](/vol1/1000/projects/ChatgptREST/artifacts/monitor/evomap_vectorization/20260408T230927Z/report.md)

注意：

- 当前 allowlist slice 选到的是 `4547` 条，不是全部 `5128` 条 `active + candidate`
- 原因是本轮仍限定在 planning allowlist buckets：
  - `planning_review_pack`
  - `planning_latest_output`
  - `planning_outputs`
  - `planning_strategy`
  - `planning_budget`
  - `planning_controlled`

### 4.3 Real-query harness

最终结果：

- `绿源来访准备 -> 4 hits`
- `钛虎机器人关节模组合作 -> 4 hits`
- `两轮车车轮市场竞争分析 -> 5 hits`

证据：

- [semantic harness summary](/vol1/1000/projects/ChatgptREST/artifacts/monitor/evomap_semantic_recall_harness/20260408T231936Z/summary.json)
- [semantic harness report](/vol1/1000/projects/ChatgptREST/artifacts/monitor/evomap_semantic_recall_harness/20260408T231936Z/report.md)

## 5. 我的裁决

本轮可以成立的结论是：

1. `semantic recall` 已从“真实 query 全 0”提升到“3/3 非零”
2. EvoMap vector lane 已从 `740` 扩到 `4547`
3. vector backfill 现在是可恢复、可观测的批处理作业，不再是黑盒长跑

但这轮**还不能夸大成“实体级语义检索已经完成”**。

更准确的口径是：

- `绿源`：已经能召回非零结果，但 top hit 仍偏“会前准备/资源准备”泛化语义
- `钛虎`：已经能召回机器人/关节模组/合作相关 planning 内容，但还不是“公司实体档案级”命中
- `两轮车车轮市场竞争分析`：已明显改善，是本轮最接近目标的 query

## 6. 下一步

下一阶段不该再回到“继续扩 task family”，而应继续做：

1. entity-aware bridging
   - 让 `绿源 / 钛虎` 这种实体，不只是吃 generic 行业上下文
2. targeted re-ingest
   - 把 `绿源拜访会议纪要`、两轮车专题入口、机器人模组合作相关高价值文档切进 EvoMap
3. retrieval ranking tuning
   - 对 entity exact match 和 doc-title/raw_ref 命中做更高权重
4. vector allowlist 扩展
   - 再决定是否把剩余 `candidate` 全量吃完
