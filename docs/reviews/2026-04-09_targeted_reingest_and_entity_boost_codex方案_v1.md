# Targeted Re-Ingest And Entity Boost Codex方案 V1

## 1. 背景

上一波 `semantic_recall_and_vector_backfill` 已把三条真实 query 从 `0 hit` 拉到非零，但质量边界仍然明显：

- `绿源来访准备` 只能命中“准备/资源”类 planning 内容，尚未稳定命中绿源实体相关纪要与会前材料
- `钛虎机器人关节模组合作` 仍主要靠 `机器人 + 关节模组 + 合作` 的桥接召回
- `两轮车车轮市场竞争分析` 已较强，但仍缺更多实体化来源与高价值 candidate 文档

本波目标不是做通用 entity registry，而是先完成两件高 ROI 工作：

1. `targeted re-ingest`
   把 planning 原始资料中与三条 query 直接相关、但尚未进入 EvoMap promoted/candidate plane 的文档定向补入
2. `entity-aware ranking boost`
   仅在 `planning explicit` surface 上，给 query 中实体词和业务强词做精确匹配加权

## 2. 真实 query

- `绿源来访准备`
- `钛虎机器人关节模组合作`
- `两轮车车轮市场竞争分析`

## 3. 先验调查结论

### 3.1 原料覆盖

- `绿源` 在 planning 原始文档中真实存在，且集中在两轮车车身业务目录
- `车轮/竞争分析` 在两轮车 planning 原始文档中覆盖较好
- `钛虎` 在 planning 原始文档中并未找到直接实体材料；本波只能继续通过 `机器人代工/关节模组/合作需求` 做桥接增强

### 3.2 之前的真正缺口

- `NoteSectionExtractor` 的常规 runtime 扫描并不覆盖 `/vol1/1000/projects/planning` 全量原始文档
- `planning explicit` fallback 只吃 allowlist bucket；普通 raw planning 文档若落到 `planning_misc`，即使入库也难以进入该 surface
- semantic recall 已有向量通道，但上游原料和 bucket 不对时，向量只能放大已有泛内容

## 4. 设计

### 4.1 受控 targeted re-ingest

- 新增受控脚本：`ops/run_planning_targeted_reingest.py`
- 只对显式 query 命中的 planning 原始 `.md` 文档执行
- 通过 `NoteSectionExtractor(path_allowlist=...)` 做 allowlist 扫描，不改默认 runtime pipeline
- 补入文档强制写入：
  - `scope_project=planning`
  - `planning_review.source_bucket=planning_controlled`
  - `planning_review.document_role=controlled`
  - `planning_review.service_readiness=high`
- 受控 candidate gate：
  - 以 `quality_auto` 为基础
  - 对显式实体/多词命中增加保守 `targeted_signal_boost`
  - 达标写入 `candidate`

### 4.2 entity-aware ranking boost

- 只作用于 `RetrievalSurface.PLANNING_EXPLICIT_PATH`
- 不触碰 `USER_HOT_PATH`
- 对 query 中实体词和业务强词在以下字段的精确匹配加权：
  - `_doc_title`
  - `_raw_ref`
  - `question`
  - `canonical_question`
  - `answer`
- `planning_controlled` 命中实体词时额外给轻微乘数加成

### 4.3 向量补齐

- 将新进入 `planning_controlled` 的 `candidate` atoms 接入 EvoMap vector lane
- 用既有 `ops/run_evomap_vectorization.py` 跑全量 governed slice 回填

## 5. 实施项

### A. extractor 协作面

- `chatgptrest/evomap/knowledge/extractors/note_section.py`
  - 支持 `path_allowlist`
  - allowlist 模式下只扫描明确指定文件

### B. retrieval 语义增强

- `chatgptrest/evomap/knowledge/retrieval.py`
  - 扩展 planning query terms/entity terms
  - `ScoredAtom` 增加 `entity_boost`
  - `planning explicit` 结果使用 entity-aware multiplier

### C. targeted re-ingest runner

- `ops/run_planning_targeted_reingest.py`
  - 发现 top-k planning 原始文档
  - 定向入库并打上 `planning_controlled`
  - 生成 run artifact

### D. 测试与 harness

- `tests/test_run_planning_targeted_reingest.py`
- `tests/test_evomap_runtime_contract.py`
- `tests/test_run_evomap_vectorization.py`
- `tests/test_run_evomap_semantic_recall_harness.py`

## 6. 验收标准

### 6.1 focused tests

- 相关 focused suite 全绿

### 6.2 live data movement

- targeted re-ingest 真实写入新的 planning controlled docs/atoms
- EvoMap vectors 明显增长

### 6.3 semantic recall

三条真实 query 全部满足：

- `hit_count > 0`
- 至少一条命中来自 `planning_controlled` 或更高价值层
- 至少在 `绿源来访准备`、`两轮车车轮市场竞争分析` 中看到更贴近实体/业务主题的 top hit

## 7. 本波明确不做

- 不做通用 entity registry
- 不改 `USER_HOT_PATH`
- 不做新的横向 task family 扩展
- 不把 `钛虎` 强行伪装成 entity-grade recall

