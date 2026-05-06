# Semantic Recall And Vector Backfill Completion Summary V1

这轮完成了两件事。

第一，`planning explicit` 的真实 query semantic recall 不再是 `0`。  
我把中文无空格 query normalization、`reviewed` status runtime visibility、planning project-scoped substring fallback 一起补上后，这 3 个真实 query 现在都能稳定返回非零：

- `绿源来访准备 -> 4`
- `钛虎机器人关节模组合作 -> 4`
- `两轮车车轮市场竞争分析 -> 5`

第二，EvoMap vector lane 做成了真正可观测的 backfill。  
这次不是一次性黑盒跑完，而是按 `batch_size=64`、`save_every_batches=1` 做周期性落盘。最终：

- `evomap_vectors.db`: `740 -> 4547`
- `records_selected = indexed = 4547`

关键证据：

- [vectorization summary](/vol1/1000/projects/ChatgptREST/artifacts/monitor/evomap_vectorization/20260408T230927Z/summary.json)
- [semantic harness summary](/vol1/1000/projects/ChatgptREST/artifacts/monitor/evomap_semantic_recall_harness/20260408T231936Z/summary.json)

这轮提交不是在宣称“实体级检索已经终局完成”，而是在把下一阶段主问题从“Phase 2 没跑通”推进到“semantic recall 已经开始可量化提升”。这点现在可以成立。
