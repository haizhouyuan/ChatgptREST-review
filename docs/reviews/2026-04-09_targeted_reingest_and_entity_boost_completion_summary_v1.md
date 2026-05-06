# Targeted Re-Ingest And Entity Boost Completion Summary V1

## 1. 结果

本波已完成：

- planning 原始资料的 `targeted re-ingest`
- `planning explicit` surface 的 `entity-aware ranking boost`
- governed slice 的向量回填
- 三条真实 query 的 live semantic recall harness

## 2. 关键 live 结果

### 2.1 targeted re-ingest

artifact:

- [summary.json](/vol1/1000/projects/ChatgptREST/artifacts/monitor/planning_targeted_reingest/20260409T004020Z/summary.json)

核心结果：

- `selected_file_count = 24`
- `docs_written = 23`
- `episodes_written = 1157`
- `atoms_written = 1833`
- `candidate_seeded = 1833`
- `staged_seeded = 0`

其中高价值新增文档包括：

- `绿源拜访会议纪要`
- `金彭绿源来访董事长汇报思路框架`
- `绿源会前4页作战包`
- `绿源 X30 对标件与切入件专题 v1`
- 多份 `关节模组` / `合作需求` / `模组代工` 资料

### 2.2 EvoMap vector backfill

artifact:

- [summary.json](/vol1/1000/projects/ChatgptREST/artifacts/monitor/evomap_vectorization/20260409T004038Z/summary.json)

before / after：

- `vectors: 4547 -> 6356`
- `records_selected = 6356`
- `planning_controlled = 1945`

### 2.3 semantic recall harness

artifact:

- [summary.json](/vol1/1000/projects/ChatgptREST/artifacts/monitor/evomap_semantic_recall_harness/20260409T005438Z/summary.json)

真实 query：

- `绿源来访准备` -> `3 hits`
- `钛虎机器人关节模组合作` -> `4 hits`
- `两轮车车轮市场竞争分析` -> `4 hits`

focused tests：

- `12/12 pass`

## 3. 质量判断

### 3.1 绿源

`绿源来访准备` 的 top hits 已从泛化“准备/资源”类内容，提升到更实体化的材料：

- `绿源拜访会议纪要`
- `金彭绿源来访董事长汇报思路框架`

这说明：

- raw material 已补入
- `planning_controlled` lane 正在生效
- entity-aware boost 确实改变了 top hit 排序

### 3.2 钛虎

`钛虎机器人关节模组合作` 仍然不是 entity-grade。

当前 top hits 主要来自：

- `LM · 普智未来合作需求`
- `关节模组调研要求`
- `104 关节模组代工` 相关摘要

这说明桥接召回是可用的，但 planning 原始库里没有 `钛虎` 实体原料，所以当前不能把它表述成“钛虎画像已经到位”。

### 3.3 两轮车车轮市场竞争分析

这条 query 继续保持较强召回，且现在更多依赖 `planning_controlled` + vector/fts 混合结果。

## 4. 代码范围

核心变更：

- [note_section.py](/vol1/1000/projects/ChatgptREST/chatgptrest/evomap/knowledge/extractors/note_section.py)
- [retrieval.py](/vol1/1000/projects/ChatgptREST/chatgptrest/evomap/knowledge/retrieval.py)
- [run_planning_targeted_reingest.py](/vol1/1000/projects/ChatgptREST/ops/run_planning_targeted_reingest.py)
- [test_evomap_runtime_contract.py](/vol1/1000/projects/ChatgptREST/tests/test_evomap_runtime_contract.py)
- [test_run_planning_targeted_reingest.py](/vol1/1000/projects/ChatgptREST/tests/test_run_planning_targeted_reingest.py)

## 5. 结论

这波不是“通用 entity framework”，而是一次高 ROI 的纠偏：

- 先把真实缺失的 planning 原料补进来
- 再让 `planning explicit` 对实体词更敏感

当前状态可以表述为：

**semantic recall 从“可用”提升到了“更贴近实体与业务主题”，但还没到完整 entity dossier 级别。**

